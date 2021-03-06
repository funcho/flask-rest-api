"""Test Api class"""

from unittest import mock

import pytest

from flask import jsonify
from flask.views import MethodView
from werkzeug.routing import BaseConverter
import marshmallow as ma
import apispec

from flask_rest_api import Api, Blueprint


class TestApi():
    """Test Api class"""

    def test_api_definition(self, app, schemas):
        DocSchema = schemas.DocSchema
        api = Api(app)
        with mock.patch.object(apispec.APISpec, 'definition') as mock_def:
            ret = api.definition('Document')(DocSchema)
        assert ret is DocSchema
        mock_def.assert_called_once_with('Document', schema=DocSchema)

    @pytest.mark.parametrize('view_type', ['function', 'method'])
    @pytest.mark.parametrize('custom_format', ['custom', None])
    @pytest.mark.parametrize('name', ['custom_str', None])
    def test_api_register_converter(self, app, view_type, custom_format, name):
        api = Api(app)
        blp = Blueprint('test', 'test', url_prefix='/test')

        class CustomConverter(BaseConverter):
            pass

        app.url_map.converters['custom_str'] = CustomConverter
        api.register_converter(
            CustomConverter, 'custom string', custom_format, name=name)

        if view_type == 'function':
            @blp.route('/<custom_str:val>')
            def test_func(val):
                return jsonify(val)
        else:
            @blp.route('/<custom_str:val>')
            class TestMethod(MethodView):
                def get(self, val):
                    return jsonify(val)

        api.register_blueprint(blp)
        spec = api.spec.to_dict()

        # If custom_format is None (default), it does not appear in the spec
        if custom_format is not None:
            parameters = [{'in': 'path', 'name': 'val', 'required': True,
                           'type': 'custom string', 'format': 'custom'}]
        else:
            parameters = [{'in': 'path', 'name': 'val', 'required': True,
                           'type': 'custom string'}]
        assert spec['paths']['/test/{val}']['get']['parameters'] == parameters

        # Converter is registered in the app iff name it not None
        if name is not None:
            assert api._app.url_map.converters[name] == CustomConverter
        else:
            assert name not in api._app.url_map.converters

    @pytest.mark.parametrize('view_type', ['function', 'method'])
    @pytest.mark.parametrize('mapping', [
        ('custom string', 'custom'),
        ('custom string', None),
        (ma.fields.Integer, ),
    ])
    def test_api_register_field(self, app, view_type, mapping):
        api = Api(app)
        blp = Blueprint('test', 'test', url_prefix='/test')

        class CustomField(ma.fields.Field):
            pass

        api.register_field(CustomField, *mapping)

        class Document(ma.Schema):
            field = CustomField()

        if view_type == 'function':
            @blp.route('/')
            @blp.arguments(Document)
            def test_func(args):
                return jsonify(None)
        else:
            @blp.route('/')
            class TestMethod(MethodView):
                @blp.arguments(Document)
                def get(self, args):
                    return jsonify(None)

        api.register_blueprint(blp)
        spec = api.spec.to_dict()

        if len(mapping) == 2:
            properties = {'field': {'type': 'custom string'}}
            # If mapping format is None, it does not appear in the spec
            if mapping[1] is not None:
                properties['field']['format'] = mapping[1]
        else:
            properties = {'field': {'type': 'integer', 'format': 'int32'}}

        assert (spec['paths']['/test/']['get']['parameters'] ==
                [{'in': 'body', 'required': True, 'name': 'body',
                  'schema': {'properties': properties, 'type': 'object'}, }])

    def test_api_extra_spec_plugins(self, app, schemas):
        """Test extra plugins can be passed to internal APISpec instance"""

        class MyPlugin(apispec.BasePlugin):
            def definition_helper(self, name, definition, **kwargs):
                return {'dummy': 'whatever'}

        api = Api(app, spec_plugins=(MyPlugin(), ))
        api.definition('Pet')(schemas.DocSchema)
        spec = api.spec.to_dict()
        assert spec['definitions']['Pet']['dummy'] == 'whatever'
