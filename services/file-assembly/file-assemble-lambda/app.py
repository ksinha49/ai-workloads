# ------------------------------------------------------------------------------
# app.py
# ------------------------------------------------------------------------------
"""
Module: app.py
Description:
  1. Fetch the original and summary PDF from S3, merge summary pages before the original.
  2. Upload the merged PDF back to S3.

Pre- and post-conditions are documented on the main handler.


Version: 1.0.2
Created: 2025-05-05
Last Modified: 2025-06-28
Modified By: Koushik Sinha

"""

from __future__ import annotations
import json
import logging
from common_utils import configure_logger, lambda_response
import os
import boto3
from PyPDF2 import PdfReader, PdfWriter
import io
from typing import Optional
from models import FileAssemblyEvent, FileAssemblyResult, LambdaResponse

# Module Metadata
__author__ = "Koushik Sinha"
__version__ = "1.0.2"
__modified_by__ = "Koushik Sinha"

"""
Logging Configuration:
    * Set the logger level to INFO
    * Create a stream handler with a custom format
    * Add the stream handler to the logger
"""

logger = configure_logger(__name__)

# Initialize the S3 client once at module load time and reuse it
s3_client = boto3.client("s3")

def upload_to_s3(pdf_bytes: bytes, file_name: str, bucket_name: str, s3_client=s3_client) -> Optional[dict]:
    """
    Upload a PDF to S3.

    Args:
        pdf_bytes (bytes): The contents of the PDF.
        file_name (str): The name of the PDF file.
        bucket_name (str): The name of the S3 bucket.

    Returns:
        dict: A dictionary containing the result of the upload operation. 
              If an error occurs, returns None.
    """
    try:
        bucket_file_name = f"{file_name}"
        response = s3_client.put_object(
            Bucket=bucket_name, Key=bucket_file_name, Body=pdf_bytes, ContentType="application/pdf"
        )
        logger.info("Uploaded file %s to S3 successfully.", bucket_file_name)
        return {"summarized_file": f"s3://{bucket_name}/{bucket_file_name}"}
    except Exception as e:
        logger.error("Error uploading to S3: %s", str(e))
        raise ValueError(f"Failed to upload PDF to S3")


def assemble_files(event: FileAssemblyEvent, context, s3_client=s3_client) -> FileAssemblyResult:
    """
    Assemble the original and summary PDFs from S3.

    Parameters
    ----------
    event : :class:`models.FileAssemblyEvent`
        Event describing the source and summary PDF locations.
    context : Any
        Lambda context (ignored).

    Returns
    -------
    :class:`models.FileAssemblyResult`
        Result of the merge operation. Errors raise ``ValueError``.
    """
    event_body = event.get("body", event)
    final_response = {}
    try:
        organic_bucket_name = event_body["organic_bucket"]
        organic_bucket_key = event_body["organic_bucket_key"]
        summary_bucket_name = event_body["summary_bucket_name"]
        summary_bucket_key = event_body["summary_bucket_key"]
        logger.info("Getting file details from S3: %s/%s", organic_bucket_name, organic_bucket_key)
        organic_response = s3_client.get_object(Bucket=organic_bucket_name, Key=organic_bucket_key)
        logger.info("GOT THE FILE DETAILS FROM THE S3: %s/%s", organic_bucket_name, organic_bucket_key)
        organic_file_content = organic_response["Body"].read()
        summary_response = s3_client.get_object(Bucket=summary_bucket_name, Key=summary_bucket_key)
        logger.info("GOT THE FILE DETAILS FROM THE S3: %s/%s", summary_bucket_name, summary_bucket_key)
        summary_file_content = summary_response["Body"].read()

        organic_file_key = event_body['organic_bucket_key']
        organic_bucket_name = event_body['organic_bucket']
        merged_file_key = organic_file_key.replace('extracted', 'merged')

        ext = os.path.splitext(organic_file_key)[1].lower()
        if ext == '.pdf':
            logger.info("Merging PDFs: %s", merged_file_key)
            merged_pdf_bytes = merge_pdfs(summary_file_content, organic_file_content)
            final_response = upload_to_s3(merged_pdf_bytes, merged_file_key, organic_bucket_name, s3_client)
            final_response['merged'] = True
        else:
            logger.info("Skipping merge for non-PDF file: %s", organic_file_key)
            final_response = upload_to_s3(summary_file_content, merged_file_key, organic_bucket_name, s3_client)
            final_response['merged'] = False
        return final_response
    except Exception as e:
        logger.error("Error assembling files: %s", str(e))
        raise ValueError(f"Failed to assemble PDFs")


def merge_pdfs(summary_file_content: bytes, organic_file_content: bytes) -> Optional[bytes]:
    """
    Merge the summary and original PDFs.

    Args:
        summary_file_content (bytes): The contents of the summary PDF.
        organic_file_content (bytes): The contents of the original PDF.

    Returns:
        bytes: The merged PDF contents. If an error occurs, returns None.
    """
    try:
        summary_pdf_reader = PdfReader(io.BytesIO(summary_file_content))
        organic_pdf_reader = PdfReader(io.BytesIO(organic_file_content))
        pdf_writer = PdfWriter()

        for page_num in range(len(summary_pdf_reader.pages)):
            pdf_writer.add_page(summary_pdf_reader.pages[page_num])

        for page_num in range(len(organic_pdf_reader.pages)):
            pdf_writer.add_page(organic_pdf_reader.pages[page_num])
        
        merge_pdf = io.BytesIO()
        pdf_writer.write(merge_pdf)
        merge_pdf.seek(0)
        return merge_pdf.read()
    except Exception as e:
        logger.error("Error merging PDFs: %s", str(e))
        raise ValueError(f"Failed to merge PDFs")




def lambda_handler(event: FileAssemblyEvent, context) -> LambdaResponse:
    """Triggered by the state machine to merge PDFs.

    Parameters
    ----------
    event : :class:`models.FileAssemblyEvent`
        Payload describing the source and summary PDFs.

    1. Calls ``assemble_files`` to download the original and summary PDFs
       from S3 and uploads the merged result.
    2. Wraps the outcome in an HTTP style response for the workflow.

    Returns
    -------
    :class:`models.LambdaResponse`
        Response payload with status information.
    """

    logger.info("Starting Lambda function...")
    try:
        final_response = assemble_files(event, context, s3_client)
        return lambda_response(200, final_response)
    except Exception as e:
        logger.error("Error in Lambda handler: %s", str(e))
        response_body = f"Error occurred: {str(e)}"
        return lambda_response(500, {"error": response_body})
