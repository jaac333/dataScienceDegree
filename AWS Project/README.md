# AquaSenseCloud — Arquitectura Cloud Serverless en AWS

Infraestructura cloud *end-to-end* para la ingesta, procesamiento y consulta de datos de sensores del Mar Menor, desplegada íntegramente como **Infraestructura como Código (CloudFormation)** sobre AWS.

> Proyecto académico (Grado en Ciencia e Ingeniería de Datos — UMU/UPCT). Desarrollado con cuentas académicas de AWS junto a Zhuxun Dong y Sergio Gallego.

---

## Visión general

El sistema combina dos subsistemas integrados:

1. **Pipeline de datos serverless y orientado a eventos**, que ingesta datos crudos, los procesa y emite alertas automáticas.
2. **Capa de servicio web en alta disponibilidad**, que expone los datos procesados mediante una API REST.

Todo el sistema se despliega de forma reproducible mediante tres plantillas de CloudFormation parametrizadas.

---

## Arquitectura

```
                          PIPELINE DE DATOS (serverless / event-driven)
   ┌────────┐   evento    ┌─────────┐   datos crudos   ┌──────────────┐
   │   S3   │ ──────────► │ Lambda1 │ ───────────────► │  DynamoDB    │
   │ bucket │             │(ingesta)│                  │ (proy-Datos) │
   └────────┘             └─────────┘                  └──────┬───────┘
                                                              │ DynamoDB Streams
                                          ┌───────────────────┼───────────────────┐
                                          ▼                                       ▼
                                    ┌──────────┐                            ┌──────────┐
                                    │ Lambda2  │                            │ Lambda3  │
                                    │(métricas)│                            │(anomalías)│
                                    └────┬─────┘                            └────┬─────┘
                                         ▼                                       ▼
                                 ┌────────────────┐                        ┌─────────┐
                                 │   DynamoDB     │                        │   SNS   │ ──► email
                                 │(proy-Resultados)│                       │ (alerta)│
                                 └───────┬────────┘                        └─────────┘
                                         │
              CAPA DE SERVICIO (alta disponibilidad, multi-AZ)
                                         ▼
   Usuario ──► ALB ──► ECS (Flask en Docker, EC2 t2.micro, autoescalado 4–6) ──► consulta proy-Resultados
                (VPC: 2 subredes públicas + 2 privadas en 2 zonas de disponibilidad, NAT, security groups)
```

---

## Pipeline de datos

- **Lambda1 — Ingesta:** se dispara al subir un CSV al bucket S3. Lee los datos de las balizas, normaliza el campo fecha (separándolo en clave de partición `Year-Month` y clave de ordenación `Day` para optimizar las consultas mensuales) e inserta con `batch_writer` para garantizar eficiencia y no perder eventos.
- **Lambda2 — Procesamiento:** se activa vía **DynamoDB Streams** ante cambios en la tabla de datos crudos. Calcula métricas (temperatura media mensual, desviación estándar, diferencia máxima de temperatura respecto al mes anterior) y las guarda en la tabla de resultados.
- **Lambda3 — Detección de anomalías:** evalúa las desviaciones típicas; si superan el umbral (0.5), acumula las fechas afectadas y envía una alerta por email vía **SNS**. Procesa los eventos en lotes de 100 para minimizar el número de correos.

## Capa de servicio web

- **API Flask** contenerizada (Docker), almacenada en **ECR** y ejecutada en un clúster **ECS** sobre instancias **EC2**.
- **Alta disponibilidad:** desplegada en 2 zonas de disponibilidad, tras un **Application Load Balancer**, con **autoescalado** (4 a 6 instancias según carga).
- **Seguridad de red:** las instancias del clúster viven en subredes privadas y solo aceptan tráfico procedente del balanceador (security groups dedicados).
- **Endpoints:** `/temp`, `/sd`, `/maxdiff` (consulta por año y mes; respuesta JSON).

---

## Servicios de AWS utilizados

| Categoría | Servicios |
|---|---|
| Cómputo | EC2, Lambda, ECS |
| Almacenamiento | S3, DynamoDB (con Streams) |
| Redes | VPC, subredes, NAT Gateway, Internet Gateway, Security Groups, ALB (Elastic Load Balancing) |
| Contenedores | ECR, ECS (clúster + servicio + task definition) |
| Escalado | Auto Scaling Group, Capacity Provider |
| Mensajería | SNS |
| IaC / Identidad | CloudFormation, IAM |

## Stack técnico

`Python` · `boto3` · `Flask` · `Docker` · `AWS CloudFormation (YAML)` · `DynamoDB` · `Lambda` · `ECS/EC2`

---

## Estructura del repositorio

- `icap_Lambda1.py` — función de ingesta S3 → DynamoDB
- `Memoria-Proy.pdf` — memoria técnica completa (arquitectura, decisiones de diseño, plantillas IaC, ejemplos de funcionamiento)
- *(plantillas CloudFormation: `proy-tablesLambdas.yaml`, `proy-network.yaml`, `proy-server.yaml`)*

## Decisiones de diseño destacadas

- **`batch_writer` en lugar de escrituras individuales:** evita la pérdida de eventos en el stream de DynamoDB y mejora la eficiencia.
- **Clave compuesta `Year-Month` / `Day`:** permite recuperar todos los datos de un mismo mes en una única consulta.
- **Procesamiento de eventos en lotes de 100:** reduce el número de notificaciones por email al agrupar más fechas por mensaje.
- **Instancias en subred privada accesibles solo vía ALB:** minimiza la superficie de exposición.
- **Mini-infraestructura intencionada:** dimensionada para pruebas con coste mínimo, documentando cómo escalar para producción.
