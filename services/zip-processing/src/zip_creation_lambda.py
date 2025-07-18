# ------------------------------------------------------------------------------
# app.py
# ------------------------------------------------------------------------------
"""
Module: app.py
Description:
  AWS Lambda to zip the metadata and summarized pdf files and save the zip file to the outbound folder


Version: 1.0.2
Created: 2025-05-12
Last Modified: 2025-06-28
Modified By: Koushik Sinha
"""
import boto3
import zipfile
import io
try:  # pragma: no cover - optional dependency
    from botocore.exceptions import BotoCoreError, ClientError
except Exception:  # pragma: no cover - allow import without botocore
    BotoCoreError = ClientError = Exception  # type: ignore
from defusedxml import ElementTree as ET
import json
import logging
from common_utils import configure_logger
from common_utils.get_ssm import get_config
import os

# ─── Logging Configuration ─────────────────────────────────────────────────────
logger = configure_logger(__name__)

# Module Metadata
__author__ = "Koushik Sinha"
__version__ = "1.0.2"
__modified_by__ = "Koushik Sinha"

# Create a custom logger formatter with timestamp, level, and log message

# Initialize boto3 clients once
ssm = boto3.client('ssm')
s3_client = boto3.client('s3')

def get_values_from_ssm(ssm_key: str) -> str:
    """
    Retrieves the value of an SSM parameter using the proxy configuration.

    Args:
        ssm_key (str): The name of the SSM parameter to retrieve.

    Returns:
        str: The value of the SSM parameter, or None if it's not found.
    """
    try:
        response = ssm.get_parameter(
            Name=ssm_key,
            WithDecryption=False
        )
        if response['Parameter']['Value']:
            logger.info("Parameter Value for %s: %s", ssm_key, response['Parameter']['Value'])
            return response['Parameter']['Value']
        else:
            logger.warning("No value found for parameter: %s", ssm_key)
            return None
    except (BotoCoreError, ClientError) as e:
        raise ValueError(f"Error occurred while retrieving parameter: {e}")

def get_environment_prefix() -> str:
    """
    Compute the SSM key prefix based on the SERVER_ENV parameter.

    Raises:
        RuntimeError: If SERVER_ENV is not set.
    """
    env = get_values_from_ssm("/parameters/aio/ameritasAI/SERVER_ENV")
    if not env:
        raise RuntimeError("SERVER_ENV not set in SSM")
    return f"/parameters/aio/ameritasAI/{env}"

def parse_s3_uri(s3_uri: str) -> (str, str, str):
    """
    Utility function to parse the S3 URI into bucket name and file key.

    Args:
        uri (str): The S3 URI.

    Returns:
        tuple: A tuple containing the bucket name, file key, and file name.
    """

    assert s3_uri.startswith("s3://"), "Invalid S3 URI"
    parts = s3_uri[5:].split("/", 2)
    bucket_name = parts[0]
    file_key = parts[1]
    file_name = parts[2]
    return bucket_name, file_key, file_name

def parse_multiple_tags(xml_content, tags):
    """Parse multiple tags from an XML string safely.

    Parameters
    ----------
    xml_content : str
        Raw XML data.
    tags : list[str]
        Tags to extract.

    Returns
    -------
    dict
        Mapping of tag name to extracted text or ``None`` if the tag is absent.
    """

    root = ET.fromstring(xml_content)
    actual_tag_content = {}
    for tag_name in tags:
        el = root.find(tag_name)
        actual_tag_content[tag_name] = el.text if el is not None else None
    return actual_tag_content

def extract_dynamic_path(path):
    """Remove the date-based prefix inserted by the ingestion pipeline."""

    # Define the length of the dynamic prefix
    prefix_length = 8  # Length of "2025/06/23/20/16/29"
    logger.info("path:%s", path)
    # Split the path by '/'
    parts = path.split('/')
    
    # Check if the path has enough parts
    if len(parts) > prefix_length:
        # Remove the initial segments and keep only the segments after the prefix
        new_parts = parts[prefix_length:]
        
        # Join the parts back together
        new_path = '/'.join(new_parts)
        
        return new_path
    else:
        return "Path does not have enough segments."
    
def assemble_zip_files(event, s3_client=s3_client):
    """
    Assemble zip files from S3 objects.

    Args:
        input_data (Dict[str, Any]): The input data containing file information.

    Returns:
        Dict[str, str]: A dictionary with the status of the assembly process.
    """
    # Get the zip file name
    zip_file_name = event['zipFileName']
    zip_file_name = zip_file_name.split("/")[-1]
    logger.info("zip_file_name:%s", zip_file_name)
    curated_prefix = get_config("CURATED_PREFIX") or os.environ.get("CURATED_PREFIX", "")
    if curated_prefix and not curated_prefix.endswith("/"):
        curated_prefix += "/"
    zip_file_name = f"{curated_prefix}{zip_file_name}"

    pdf_files = [file['pdffile'] for file in event.get('pdfFiles', [])]
    xml_files = event.get('xmlFiles', [])
    # Create a zip file
    output_zip_stream = io.BytesIO()
    unprocessedFileMessage = []
    processedFiles = []
    xml_tags = ["PolNumber","TrackingID"] 

    with zipfile.ZipFile(output_zip_stream, 'w', zipfile.ZIP_DEFLATED) as output_zip:
        for xml_file in xml_files:
            bucket_name, file_key, file_name = parse_s3_uri(xml_file)
            response = s3_client.get_object(Bucket=bucket_name, Key=f"{file_key}/{file_name}")
            file_name = extract_dynamic_path(file_name)
            logger.info("file_name:%s", file_name)
            output_zip.writestr(file_name, response['Body'].read())
        # Check if Output is present and summarized_file exists
        for file in event.get("files", []):
            summary_file = file.get("processedFiles")
            if "Output" in summary_file:
                summary_json = json.loads(summary_file["Output"])
                summarized = summary_json.get("body", {}).get("summarized_file")
                if summarized:
                  bucket_name, file_key, file_name = parse_s3_uri(summarized)
                  parts = file_name.split("/")
                  parts = parts[-1].split(".", 1)
                  processedFiles.append(parts[0])
                  pdf_file_name = f"{parts[0]}.pdf"
                  response = s3_client.get_object(Bucket=bucket_name, Key=f"{file_key}/{file_name}")

                  file_name = extract_dynamic_path(file_name)
                  logger.info("file_name:%s", file_name)
                  output_zip.writestr(file_name, response['Body'].read())

        for pdf_file in pdf_files:
            bucket_name, file_key, file_name = parse_s3_uri(pdf_file)
            parts = file_name.split("/")
            parts = parts[-1].split(".", 1)
            if parts[0] not in processedFiles:
              response = s3_client.get_object(Bucket=bucket_name, Key=f"{file_key}/{file_name}")
              file_name = extract_dynamic_path(file_name)
              logger.info("file_name:%s", file_name)
              output_zip.writestr(file_name, response['Body'].read())
    # Save the zip file to S3
    output_zip_stream.seek(0)
    destination_zip_key = f"{zip_file_name}"
    pdf_file_path = pdf_files[0]
    distination_bucket_name, distinationfile_key, distinationfile_name  = parse_s3_uri(pdf_file_path)
    try:
        s3_client.put_object(
            Bucket=distination_bucket_name,
            Key=destination_zip_key,
            Body=output_zip_stream.getvalue(),
        )
    except ClientError as e:
        logger.error("Failed to upload zip file to S3: %s", e)
        return {
            "statusCode": 500,
            "error": "Failed to upload zip file",
        }

    for xml_file in xml_files:
            bucket_name, key, file_name = parse_s3_uri(xml_file)
            file_key = f"{key}/{file_name}"
            try:
                xml_response = s3_client.get_object(Bucket=bucket_name, Key=file_key)
                xml_content = xml_response['Body'].read()
                #xml_file_name = file_name.split(".")[0]
                xml_file_name = file_name.split("/")
                xml_file_name = xml_file_name[-1].split(".", 1)
                xml_file_name = xml_file_name[0]
                xml_actual_content = xml_content.decode('utf-8')
                if xml_file_name not in processedFiles:
                    xml_tag_content = parse_multiple_tags(xml_actual_content, xml_tags)
                    pdf_file_name =f"{xml_file_name}.pdf"
                    unprocessedFileMessage.append((xml_tag_content["PolNumber"],xml_tag_content["TrackingID"],pdf_file_name) )  
            except ClientError as e:
                logger.error("Failed to retrieve XML from S3: %s", e)
                raise e

    try:
         if unprocessedFileMessage:
             raise ValueError(f"Failed process the files inside the zip file")
         else:
            return  {"status": "200",
                "statusMessage" : "All the files in the zip file got processed"
                }
    except ValueError as e:
       error_header = (
          "The below policies encountered an error and could not produce a summary. The APS will still be available in TPP.\n\n"
       )
       columns = "{:<20} {:<35} {:<35}\n".format("Policy Number", "Tracking ID", "File Name")
       rows = unprocessedFileMessage
       message = error_header + columns
       for row in rows:
          message += "{:<20} {:<35} {:<20}\n".format(*row)
       return  {"status": "400",
                "unprocessedFiles" : message
                }
          

def lambda_handler(event: dict, context) -> dict:
    """Triggered by the workflow to package summary outputs.

    1. Downloads the metadata and summary PDFs from S3 and zips them into a
       single archive.
    2. Stores the archive in the outbound folder for delivery.

    Returns a dictionary indicating success or failure.
    """

    return assemble_zip_files(event, s3_client)
