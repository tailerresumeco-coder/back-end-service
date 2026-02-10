import os
import boto3
from io import BytesIO

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