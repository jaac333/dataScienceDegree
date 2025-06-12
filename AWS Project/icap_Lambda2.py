import boto3
from boto3.dynamodb.conditions import Key, Attr
from decimal import Decimal
import json

TABLE1_NAME = 'proy-Datos'
TABLE2_NAME = 'proy-Resultados'

dynamodb = boto3.resource('dynamodb')
table1 = dynamodb.Table(TABLE1_NAME)
table2 = dynamodb.Table(TABLE2_NAME)


def get_previous_month(date):
    previous_month = date.split('-')
    if previous_month[1] == '01':
        previous_month[0] = str(int(previous_month[0])-1)
        previous_month[1] = '12'
        
    else:
        previous_month[1] = f'{(int(previous_month[1])-1):02}'

    return '-'.join(previous_month)

def get_next_month(date):
    next_month = date.split('-')
    if next_month[1] == '12':
        next_month[0] = str(int(next_month[0])+1)
        next_month[1] = '01'
        
    else:
        next_month[1] = f'{(int(next_month[1])+1):02}'

    return '-'.join(next_month)


def get_items(current_date):
    items = table1.query(KeyConditionExpression=Key('YearMonth').eq(current_date))['Items']
    return items


def get_metrics(items, previous_month_items):
    previous_month_avg = 0.0
    if previous_month_items:
        for item in previous_month_items:
            if float(item['Medias']) > previous_month_avg:
                previous_month_avg = float(item['Medias'])
    
    medias = [float(items[i]['Medias']) for i in range(len(items))]
    desviaciones = [float(items[i]['Desviaciones']) for i in range(len(items))]

    max_sd = max(desviaciones)
    media_mensual = sum(medias) / len(medias)

    if previous_month_avg > 0:
        diff = max(medias) - previous_month_avg
    else:
        diff = 0.0
    
    return {'YearMonth' : items[0]['YearMonth'],
            'maxdiff' : float(diff),
            'sd' : float(max_sd),
            'temp' :float(media_mensual)}



#Esto estaba pensado para procesar multiples modificaciones a la vez, pero para 1 tambien funciona correctamente
def lambda_handler(event, context):

    inserted_or_modified = set()

    for e in event['Records']:
        date = e['dynamodb']['Keys']['YearMonth']['S']
        inserted_or_modified.add(date)
    
    inserted_or_modified = list(inserted_or_modified)
    new_rows = []
    
    for date in inserted_or_modified:
        items = get_items(date)
        previous_month_items = get_items(get_previous_month(date))
        row = get_metrics(items=items, previous_month_items=previous_month_items)
        new_rows.append(row)
        
        next_month_items = get_items(get_next_month(date))
        if next_month_items:
            next_month_row = get_metrics(items=next_month_items, previous_month_items=items)
            new_rows.append(next_month_row)
    
    for row in new_rows:
        table2.put_item(Item= json.loads(json.dumps(row), parse_float=Decimal))

    return 'FINISHED!'