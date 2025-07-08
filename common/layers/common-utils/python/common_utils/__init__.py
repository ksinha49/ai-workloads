# Module Metadata
__author__ = "Koushik Sinha"
__version__ = "1.0.0"
__modified_by__ = "Koushik Sinha"

import os
import sys
import site

from .logging_utils import configure_logger
from .get_ssm import (
    get_values_from_ssm,
    get_environment_prefix,
    parse_s3_uri,
    get_config,
)

# Optional path to Python packages installed on an attached EFS volume.
_EFS_DEPENDENCY_PATH = os.environ.get("EFS_DEPENDENCY_PATH") or get_config(
    "EFS_DEPENDENCY_PATH"
)
if _EFS_DEPENDENCY_PATH:
    for p in (_EFS_DEPENDENCY_PATH, os.path.join(_EFS_DEPENDENCY_PATH, "python")):
        if os.path.isdir(p) and p not in sys.path:
            site.addsitedir(p)

# Optional base directory for models stored on EFS.
MODEL_EFS_PATH = os.environ.get("MODEL_EFS_PATH") or get_config("MODEL_EFS_PATH")
from .get_secret import get_secret
from .milvus_client import MilvusClient, VectorItem, SearchResult, GetResult
from .elasticsearch_client import ElasticsearchClient
from .entity_extraction import extract_entities
from .lambda_response import lambda_response
from .error_utils import log_exception, error_response
from .ner_models import load_ner_model
from .s3_utils import iter_s3_records

__all__ = [
    "get_values_from_ssm",
    "get_environment_prefix",
    "parse_s3_uri",
    "get_config",
    "get_secret",
    "MilvusClient",
    "VectorItem",
    "SearchResult",
    "GetResult",
    "ElasticsearchClient",
    "extract_entities",
    "configure_logger",
    "lambda_response",
    "log_exception",
    "error_response",
    "load_ner_model",
    "iter_s3_records",
]
