import importlib.util


def load_lambda(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_generate_acord_xml():
    module = load_lambda('acord', 'services/acord-generator/src/generate_xml_lambda.py')
    data = {
        'fields': {'PolNumber': 'PN123', 'InsuredName': 'Jane Doe'},
        'signatures': {'Insured': 'Jane Doe', 'DateSigned': '2024-01-01'},
    }
    xml = module.generate_acord_xml(data)
    assert '<PolNumber>PN123</PolNumber>' in xml
    assert '<InsuredName>Jane Doe</InsuredName>' in xml
    assert '<Insured>Jane Doe</Insured>' in xml
    assert '<DateSigned>2024-01-01</DateSigned>' in xml
