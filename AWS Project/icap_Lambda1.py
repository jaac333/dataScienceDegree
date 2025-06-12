import json, urllib, boto3, csv
import datetime
from decimal import Decimal

TABLE_NAME = 'proy-Datos'
BUCKET_NAME =  'proydatabucket'


s3 = boto3.resource('s3')
dynamodb = boto3.resource('dynamodb', region_name='us-east-1')
table = dynamodb.Table(TABLE_NAME)

def lambda_handler(event, context):

  bucket = BUCKET_NAME
  key = urllib.parse.unquote_plus(event['Records'][0]['s3']['object']['key'])
  localFilename = '/tmp/Temperaturas.csv'

  try:
    s3.meta.client.download_file(bucket, key, localFilename)
  except Exception as e:
    print('Error getting object {} from bucket {}. Make sure they exist and your bucket is in the same region as this function.'.format(key, bucket))
    raise e
  
  with open(localFilename) as csvfile:
    reader = csv.DictReader(csvfile, delimiter=',')
    items = {}
    for row in reader:
      try:
        fecha = str(datetime.datetime.strptime(row['Fecha'],'%Y/%m/%d').date()).split('-')
        year_month = '-'.join(fecha[:2])
        day = fecha[2]

        items[(year_month, day)] = {
              'YearMonth': year_month,
              'Day': day,
              'Medias':   float(row['Medias']),
              'Desviaciones':  float(row['Desviaciones'])
              }

      except Exception as e:
         print(e)
         print("Unable to insert data into DynamoDB table".format(e))
      
  with table.batch_writer() as batch:
    for _,item in items.items():
      batch.put_item(Item=json.loads(json.dumps(item), parse_float=Decimal))

  return 'FINISHED!'
