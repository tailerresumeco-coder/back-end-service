import os
import boto3
import json
from io import BytesIO
import uuid

AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")
AWS_REGION = os.getenv("AWS_REGION")

def upload_file_to_s3(file_bytes: bytes, bucket_name: str, object_name: str):
    s3_client = boto3.client("s3", region_name=AWS_REGION)

    # ✅ Wrap bytes in file-like object
    file_obj = BytesIO(file_bytes)

    s3_client.upload_fileobj(
        Fileobj=file_obj,
        Bucket=bucket_name,
        Key=object_name,
        ExtraArgs={"ContentType": "application/pdf"}
    )

    return f"https://{bucket_name}.s3.{AWS_REGION}.amazonaws.com/{object_name}"

async def get_json_resume_from_s3(bucket_name: str, object_name: str):
    s3_client = boto3.client("s3", region_name=AWS_REGION)

    try:
        response = s3_client.get_object(
            Bucket=bucket_name,
            Key=object_name
        )

        data = response["Body"].read().decode("utf-8")

        # ✅ convert back to dict
        return json.loads(data)

    except s3_client.exceptions.NoSuchKey:
        return {
            "status": "error",
            "message": "File not found in S3"
        }

    except Exception as e:
        return {
            "status": "error",
            "message": str(e)
        }

async def upload_json_resume_to_s3(resume_id: str, json_resume: dict, bucket_name: str, object_name: str):
    s3_client = boto3.client(
        "s3",
        region_name=AWS_REGION,
        aws_access_key_id=AWS_ACCESS_KEY_ID,
        aws_secret_access_key=AWS_SECRET_ACCESS_KEY
    )

    response = s3_client.put_object(
        Bucket=bucket_name,
        Key = resume_id,
        Body=json.dumps(json_resume).encode("utf-8"),
        ContentType="application/json"
    )
    is_success = response["ResponseMetadata"]["HTTPStatusCode"] == 200

    return is_success