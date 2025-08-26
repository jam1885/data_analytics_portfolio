"""
Python script that reads weather conditions and sends a daily user Discord notification.

AWS EventBridge runs this script daily through Lambda to scrape weather from an API call,
then checks if the weather has been hot and dry for more than 5 consecutive days.

The daily high temperature and expected rainfall total are stored in a DynamoDB table.
A counter of hot days since the last rainfall is stored in a separate DynamoDB table.
"""

 # imports
import os
import boto3
from botocore.exceptions import ClientError
from datetime import datetime
import requests
import json

"""" define global variables """
# url webpage for reading weather data
# weather api forecast
weatherAPI_url_forecast = "http://api.weatherapi.com/v1/forecast.json?key=79c5888d4c90495b921162215252804&q=30080&days=1&aqi=no&alerts=no"
# weatherAPI_url_current = "http://api.weatherapi.com/v1/forecast.json?key=79c5888d4c90495b921162215252804&q=30080&days=1&aqi=no&alerts=no"

# Initialize AWS clients
region_name = "us-east-2"
dynamodb = boto3.client("dynamodb")

# get weatherAPI data as json body and store in Python dict
def get_weatherAPI_json(url: str) -> dict:
    try:
        weather_body = requests.get(url)
    except requests.exceptions.RequestException as e:
        raise e
    
    weather_dict = json.loads(weather_body.text)
    return weather_dict

# write date, high temp, and expected rainfall into DynamoDB table
def upload_data(high_temp: float, rain_exp: float, table_name: str):
    # get date to record in table
    date_str = datetime.today().strftime('%m-%d-%Y')
    
    # Add today's weather data to table
    try:
        dynamodb.put_item(
            TableName=table_name,
            Item={
                "date": {"S": date_str},
                "High": {"N": f"{high_temp:.2f}"},
                "Rainfall": {"N": f"{rain_exp:.2f}"} 
                }
        )
    except ClientError as e:
        raise e

# Update DynamoDB table with hot weather counter
def get_and_increment_counter(table_name: str, increment_flag: bool = True, key_id: str = "Counter") -> int:
    """
    Atomically read, increment, and return the counter from DynamoDB.

    Args:
        table_name (str): Name of the DynamoDB table.
        increment_flag (bool): Logical flag to determine whether to increment Counter.
        key_id (str): The ID of the counter item. Defaults to "Counter".

    Returns:
        int: The updated counter value.
    """
    key = {"ID": {"S": key_id}}

    if increment_flag:
        response = dynamodb.update_item(
            TableName=table_name,
            Key=key,
            UpdateExpression="SET #c = if_not_exists(#c, :start) + :inc",
            ExpressionAttributeNames={"#c": "Count"},
            ExpressionAttributeValues={":inc": {"N": "1"}, ":start": {"N": "0"}},
            ReturnValues="UPDATED_NEW"
        )
        counter = int(response["Attributes"]["Count"]["N"])
    else:
        response = dynamodb.get_item(
            TableName=table_name,
            Key=key
        )
        if "Item" in response and "Count" in response["Item"]:
            counter = int(response["Item"]["Count"]["N"])
        else:
            counter = 0  # default if item doesn’t exist

    return counter

# Function to send notification message to Discord channel through a webhook.
def send_notification(num: int):

    # Create a Secrets Manager client
    session = boto3.session.Session()
    client = session.client(
            service_name='secretsmanager',
            region_name=region_name
        )
    
    # Read secret name from environment variable
    secret_name = os.environ["SECRET_NAME"]

    try:
        get_secret_value_response = client.get_secret_value(
            SecretId=secret_name
        )
    except ClientError as e:
        # For a list of exceptions thrown, see
        # https://docs.aws.amazon.com/secretsmanager/latest/apireference/API_GetSecretValue.html
        raise e

    secret = get_secret_value_response['SecretString']
    secret_dict = json.loads(secret)
    webhook_url = secret_dict["WEBHOOK_URL"].strip()

    # send POST to Discord webhook
    msg = {
         "content": f"It has been {num} hot days since it rained"
    }
    r = requests.post(webhook_url, json=msg, timeout=5.0)
    print(f"r.status_code")
    if r.status_code != 204:
        print(f"Failed to send Discord alert. Status code: {r.status_code}")

def lambda_handler(event, context):
    weather_response = get_weatherAPI_json(weatherAPI_url_forecast)
    weather_forecast = weather_response['forecast']['forecastday'][0]['day']
    max_temp_f = weather_forecast['maxtemp_f']
    total_precip_in = weather_forecast['totalprecip_in']
    upload_data(max_temp_f, total_precip_in, os.environ["WEATHER_TABLE"])

    if max_temp_f > 85 and total_precip_in < 0.05:
         weather_flag = True
    else:
         weather_flag = False
    
    counter = get_and_increment_counter(os.environ["COUNTER_TABLE"], weather_flag)
    send_notification(counter)
