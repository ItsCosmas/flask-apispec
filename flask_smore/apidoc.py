# -*- coding: utf-8 -*-

import types

import six
from smore import swagger
from smore.apispec.core import VALID_METHODS

from flask_smore import ResourceMeta
from flask_smore.paths import rule_to_path, rule_to_params
from flask_smore.utils import resolve_refs, merge_recursive, filter_recursive

class Documentation(object):

    def __init__(self, app, spec):
        self.app = app
        self.spec = spec
        self.view_converter = ViewConverter(app, spec)
        self.resource_converter = ResourceConverter(app, spec)

    def register(self, target, endpoint=None, blueprint=None):
        if isinstance(target, types.FunctionType):
            self.view_converter.convert(target, endpoint, blueprint)
        elif isinstance(target, ResourceMeta):
            self.resource_converter.convert(target, endpoint, blueprint)
        else:
            raise TypeError

class Converter(object):

    def __init__(self, app, spec):
        self.app = app
        self.spec = spec

    def convert(self, target, endpoint=None, blueprint=None):
        endpoint = endpoint or target.__name__.lower()
        if blueprint:
            endpoint = '{}.{}'.format(blueprint, endpoint)
        rules = self.app.url_map._rules_by_endpoint[endpoint]
        for rule in rules:
            self.spec.add_path(**self.get_path(rule, target))

    def get_path(self, rule, target):
        operations = self.get_operations(rule, target)
        parent = self.get_parent(target)
        return {
            'view': target,
            'path': rule_to_path(rule),
            'operations': {
                method.lower(): self.get_operation(rule, view, parent=parent)
                for method, view in six.iteritems(operations)
                if method.lower() in (set(VALID_METHODS) - {'head'})
            },
        }

    def get_operations(self, rule, target):
        return {}

    def get_operation(self, rule, view, parent=None):
        docs = merge_recursive(
            getattr(view, '__apidoc__', {}),
            getattr(parent, '__apidoc__', {}),
        )
        operation = {
            'responses': self.get_responses(view, parent),
            'parameters': self.get_parameters(rule, view, docs, parent),
        }
        docs.pop('params', None)
        return merge_recursive(operation, docs)

    def get_parent(self, view):
        return None

    def get_parameters(self, rule, view, docs, parent=None):
        __args__ = resolve_refs(parent, merge_recursive(*getattr(view, '__args__', [])))
        return swagger.args2parameters(
            __args__.get('args', {}),
            default_in=__args__.get('default_in'),
        ) + rule_to_params(rule, docs.get('params'))

    def get_responses(self, view, parent=None):
        ret = resolve_refs(parent, merge_recursive(*getattr(view, '__schemas__', [])))
        predicate = lambda key, value: not(
            hasattr(key, 'startswith') and
            key.startswith('_')
        )
        return filter_recursive(ret, predicate)

class ViewConverter(Converter):

    def get_operations(self, rule, view):
        return {method: view for method in rule.methods}

class ResourceConverter(Converter):

    def get_operations(self, rule, resource):
        return {
            method: getattr(resource, method.lower())
            for method in rule.methods
            if hasattr(resource, method.lower())
        }

    def get_parent(self, resource):
        return resource
