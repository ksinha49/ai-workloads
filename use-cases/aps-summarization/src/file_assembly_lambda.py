import importlib.util
import os

MODULE_PATH = os.path.join(os.path.dirname(__file__), '..', '..', 'services', 'file-assembly', 'src', 'file_assembly_lambda.py')

spec = importlib.util.spec_from_file_location('file_assembly_lambda', MODULE_PATH)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def lambda_handler(event, context):
    """Wrapper that delegates to the shared file assembly lambda."""
    return module.lambda_handler(event, context)
