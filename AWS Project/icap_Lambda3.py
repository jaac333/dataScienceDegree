import boto3
import json
def lambda_handler(event, context):
    message = None
    fechas = []
    desviaciones = []
    for record in event['Records']:
        newImage = record['dynamodb'].get('NewImage', None)
        if newImage:        #Desviaciones": {"N": "0.4037204384803772"}
            desviacion = float(record['dynamodb']['NewImage']['Desviaciones']['N'])
            if desviacion is not None and float(desviacion) > 0.5:
                fecha = record['dynamodb']['NewImage']['YearMonth']['S']
                dia = record['dynamodb']['NewImage']['Day']['S']
                fechas.append(f"{fecha}-{dia}")
                desviaciones.append(desviacion)
    if fechas and desviaciones:
        sns = boto3.client('sns')
        alertTopic = 'DeviationExceeded'
        snsTopicArn = [t['TopicArn'] for t in sns.list_topics()['Topics'] if t['TopicArn'].lower().endswith(':' + alertTopic.lower())][0]
        message = "Deviation exceeded on the following dates:\n" + "\n".join([f"{fecha}: {desviacion:.3f}" for fecha, desviacion in zip(fechas, desviaciones)])
        sns.publish(
            TopicArn=snsTopicArn,
            Subject='Desviación Alta Detectada',
            Message=message,
            MessageStructure='raw'
        )
    return 'Updated'