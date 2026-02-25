#!/usr/bin/python3
"""
Download + prepare a small Ensembl RNA FASTA subset for tiny Transformer training.

- Auto-discovers the latest Ensembl file from the /current_fasta/<species>/<category>/ directory
- Streams and decompresses .fa.gz on the fly
- Cleans sequences: uppercase, T->U, filters by length and allowed chars
- Deduplicates exact sequences
- Randomly samples a target number of sequences
- Writes out a compact FASTA

Usage (examples):
  python prep_ensembl_rna_subset.py --species homo_sapiens --category ncrna \
      --out data/rna_small.fasta --target 10000 --min_len 60 --max_len 512 --seed 42

  # mRNA (cDNA) instead of ncRNA:
  python prep_ensembl_rna_subset.py --species homo_sapiens --category cdna --target 20000

"""
import argparse, gzip, io, os, random, re, sys, urllib.request
from urllib.error import HTTPError, URLError

INDEX_PATTERN = re.compile(r'href="([^"]+\.fa\.gz)"', re.IGNORECASE)
BASE_URL = "https://ftp.ensembl.org/pub/current_fasta/{species}/{category}/"

def fetch_index(url: str) -> str:
    with urllib.request.urlopen(url) as r:
        return r.read().decode("utf-8", errors="replace")

def pick_fasta_url(index_html: str, base: str) -> str:
    candidates = INDEX_PATTERN.findall(index_html)
    print(f"[debug] Found {len(candidates)} .fa.gz candidates:")
    # Prefer species-wide “.ncrna.fa.gz” or “.cdna.all.fa.gz” style files
    # but fall back to the first .fa.gz we see.
    preferred = [c for c in candidates if c.endswith((".ncrna.fa.gz",".cdna.all.fa.gz",".cdna.fa.gz",".ncrna.all.fa.gz"))]
    fname = preferred[0] if preferred else (candidates[0] if candidates else None)
    if not fname:
        raise RuntimeError("No .fa.gz files found in the index.")
    if fname.startswith("http://") or fname.startswith("https://"):
        return fname
    return urllib.request.urljoin(base, fname)

def stream_gzip_lines(url: str):
    # Stream download and decompress line-by-line to avoid temp files
    with urllib.request.urlopen(url) as resp:
        gz = gzip.GzipFile(fileobj=io.BytesIO(resp.read())) if resp.length and resp.length < 50_000_000 else None
        if gz is None:
            # For large files, stream incrementally
            decompressor = gzip.GzipFile(fileobj=None)
            buf = io.BytesIO()
            chunk = resp.read(8192)
            while chunk:
                buf.write(chunk)
                chunk = resp.read(8192)
            buf.seek(0)
            with gzip.GzipFile(fileobj=buf) as gzf:
                for line in gzf:
                    yield line
        else:
            for line in gz:
                yield line

def fasta_iter_from_stream(lines_bytes):
    header = None
    seq_chunks = []
    for bline in lines_bytes:
        line = bline.decode("utf-8", errors="ignore").rstrip("\n\r")
        if not line:
            continue
        if line.startswith(">"):
            if header is not None:
                yield header, "".join(seq_chunks)
            header = line[1:].strip()
            seq_chunks = []
        else:
            seq_chunks.append(line)
    if header is not None:
        yield header, "".join(seq_chunks)

def clean_seq(seq: str):
    seq = seq.upper().replace("T","U")
    # Keep only A,C,G,U,N (drop other IUPAC codes)
    allowed = set("ACGUN")
    if not set(seq).issubset(allowed):
        # Replace disallowed with N, then we can filter by max N-fraction if desired
        seq = "".join(ch if ch in allowed else "N" for ch in seq)
    return seq

def write_fasta(path, records):
    with open(path, "w") as out:
        for hdr, seq in records:
            out.write(f">{hdr}\n")
            # Wrap to 80 cols (nice to read; optional)
            for i in range(0, len(seq), 80):
                out.write(seq[i:i+80] + "\n")

def main():
    #Con este objeto ArgumentParser, proveniente del módulo estándar argparse de Python, podemos construir una interfaz 
    #que nos permita seleccionar características sobre el fichero .py actual, desde la línea de comandos.
    #Así definimos que opciones se le pueden pasar al comando <python script.py > a la hora de ejecutarlo desde la línea de comandos

    ap = argparse.ArgumentParser(description="Prepare a small Ensembl RNA FASTA subset.")
    ap.add_argument("--species", default="homo_sapiens", help="Ensembl species path (e.g., homo_sapiens, mus_musculus)")
    ap.add_argument("--category", default="ncrna", choices=["ncrna","cdna"], help="FASTA category: ncrna or cdna")
    ap.add_argument("--out", default="data/alternative/rna_small.fasta", help="Output FASTA path")
    ap.add_argument("--target", type=int, default=50000, help="Target number of sequences to sample")
    ap.add_argument("--min_len", type=int, default=60, help="Minimum sequence length to keep")
    ap.add_argument("--max_len", type=int, default=512, help="Maximum sequence length to keep")
    ap.add_argument("--max_N_frac", type=float, default=0.2, help="Drop sequences with > this fraction of N")
    ap.add_argument("--seed", type=int, default=42, help="Random seed for sampling")
    ap.add_argument("--direct_url", default=None, help="Optional direct URL to a .fa.gz (skips index discovery)")
    args = ap.parse_args()

    #Véase como en los argumentos que se definen, tenemos que se toman solo 10.000 secuencias

    random.seed(args.seed)
    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)

    #Visitamos la URL, con tal de poder 
    try:
        if args.direct_url:
            fasta_url = args.direct_url
            print(f"[debug] Direct URL provided by user: {fasta_url}")
        else:
            idx_url = BASE_URL.format(species=args.species, category=args.category)
            print(f"[debug] Base index URL: {idx_url}")
            print(f"[info] Discovering latest file at: {idx_url}")
            html = fetch_index(idx_url)   #Esta función descarga el contenido de una url
            print("[debug] Successfully fetched index HTML.")
            fasta_url = pick_fasta_url(html, idx_url)
            print(f"[debug] Picked FASTA URL: {fasta_url}")
        print(f"[info] Downloading/streaming: {fasta_url}")
    except (HTTPError, URLError, RuntimeError) as e:
        print(f"[error] Could not locate FASTA: {e}", file=sys.stderr)
        sys.exit(1)

    # First pass: collect acceptable sequences (header, cleaned seq) into a reservoir sample
    # to avoid storing everything in memory for giant files.
    reservoir = []
    seen = set()  # exact-sequence dedup
    kept = 0
    total = 0

    def consider_record(h, s):
        nonlocal kept, total
        total += 1
        s_clean = clean_seq(s)
        if not (args.min_len <= len(s_clean) <= args.max_len):
            return
        if (s_clean.count("N") / len(s_clean)) > args.max_N_frac:
            return
        if s_clean in seen:
            return
        seen.add(s_clean)

        # Reservoir sampling to cap memory at ~target
        if len(reservoir) < args.target:
            reservoir.append((h, s_clean))
        else:
            j = random.randint(0, total - 1)
            if j < args.target:
                reservoir[j] = (h, s_clean)
        kept += 1

    try:
        lines = stream_gzip_lines(fasta_url)
        for hdr, seq in fasta_iter_from_stream(lines):
            consider_record(hdr, seq)
            if total % 50000 == 0 and total > 0:
                print(f"[progress] seen={total:,} kept={kept:,} sample_size={len(reservoir):,}")
    except (HTTPError, URLError) as e:
        print(f"[error] Download failed: {e}", file=sys.stderr)
        sys.exit(1)

    # Shuffle final reservoir for variety and write
    random.shuffle(reservoir)
    write_fasta(args.out, reservoir)
    print(f"[done] wrote {len(reservoir):,} sequences to {args.out}")
    print(f"[stats] total_seen={total:,}, unique_kept={kept:,}, min_len={args.min_len}, max_len={args.max_len}")

if __name__ == "__main__":
    main()
