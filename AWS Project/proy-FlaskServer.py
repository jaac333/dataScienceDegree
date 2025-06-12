from flask import Flask, request, jsonify, redirect, url_for
import boto3
from boto3.dynamodb.conditions import Key
import os
from ec2_metadata import ec2_metadata

TABLE = 'proy-Resultados'

db = boto3.resource('dynamodb', region_name='us-east-1')
table = db.Table(TABLE)
ipv4 = ec2_metadata.private_ipv4

app = Flask(__name__)


@app.route('/')
def index():
    title = '<h1> You look kinda lost... But there you go a poem! </h1>'
    content = '<h2> Cuando el mar sea redondo</h2>' + '<h2>y el sol deje de brillar,</h2>' + '<h2>ese será el día</h2>' + '<h2>en que te pueda olvidar. </h2>'

    return title + content


@app.route('/maxdiff', methods=['GET'])
def maxdiff():
    month = request.args['month']
    month = f'{int(month):02}'
    year = request.args['year']
    date = '-'.join([year,month])
    item = table.query(KeyConditionExpression=Key('YearMonth').eq(date))['Items'][0]

    result = {}
    if item:
        maxdiff = item['maxdiff']
        result['Date'] = date
        result['Maxdiff'] = maxdiff
        result['ip'] = ipv4
        result = jsonify(result)
    else:
        result = '<h1>We currently do not have data of the requested date :(...</h1>'

    return result


@app.route('/sd')
def sd():
    month = request.args['month']
    month = f'{int(month):02}'
    year = request.args['year']
    date = '-'.join([year,month])
    item = table.query(KeyConditionExpression=Key('YearMonth').eq(date))['Items'][0]

    result = {}
    if item:
        sd = item['sd']
        result['Date'] = date
        result['sd'] = sd
        result['ip'] = ipv4
        result = jsonify(result)
    else:
        result = '<h1>We currently do not have data of the requested date :(...</h1>'

    return result


@app.route('/temp')
def temp():
    month = request.args['month']
    month = f'{int(month):02}'
    year = request.args['year']
    date = '-'.join([year,month])
    item = table.query(KeyConditionExpression=Key('YearMonth').eq(date))['Items'][0]

    result = {}
    if item:
        temp = item['temp']
        result['Date'] = date
        result['temp'] = temp
        result['ip'] = ipv4
        result = jsonify(result)
    else:
        result = '<h1>We currently do not have data of the requested date :(...</h1>'

    return result


@app.errorhandler(Exception)
def handle_unexpected_error(error):
    return redirect(url_for('index')) 


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=True, host='0.0.0.0', port=port)