from multiprocessing import Pool
import tldextract
import boto3
import os
import sys
import datetime
import tzlocal
import argparse
import json


class FireProx(object):
	def __init__(self, arguments):
		self.access_key = arguments.access_key
		self.secret_access_key = arguments.secret_access_key
		self.command = arguments.command
		self.api_id = arguments.api_id
		self.url = arguments.url
		self.api_list = []
		self.client = None

		if not self.load_creds():
			self.error('Unable to load AWS credentials')

		if not self.command:
			self.error('Please provide a valid command')


	def __str__(self):
		return 'FireProx()'


	def load_creds(self):
		try:
			client = boto3.client('apigateway')
			client.get_account()
			self.client = client
			return True
		except:
			pass

		try:
			client = boto3.client(
				'apigateway',
				aws_access_key_id=self.access_key,
				aws_secret_access_key=self.secret_access_key
			)
			client.get_account()
			self.client = client
			return True
		except:
			pass

		return False


	def error(self, error):
		parser.print_help()
		sys.exit(error)


	def get_template(self):
		url = self.url
		if url[-1] == '/':
			url = url[:-1]

		title = 'fireprox_{}'.format(
			tldextract.extract(url).domain
		)
		version_date = f'{datetime.datetime.now():%Y-%m-%dT%XZ}'
		template = '''
		{
		  "swagger": "2.0",
		  "info": {
			"version": "{{version_date}}",
			"title": "{{title}}"
		  },
		  "basePath": "/",
		  "schemes": [
			"https"
		  ],
		  "paths": {
			"/{proxy+}": {
			  "x-amazon-apigateway-any-method": {
				"produces": [
				  "application/json"
				],
				"parameters": [
				  {
					"name": "proxy",
					"in": "path",
					"required": true,
					"type": "string"
				  }
				],
				"responses": {},
				"x-amazon-apigateway-integration": {
				  "uri": "{{url}}/{proxy}",
				  "responses": {
					"default": {
					  "statusCode": "200"
					}
				  },
				  "requestParameters": {
					"integration.request.path.proxy": "method.request.path.proxy"
				  },
				  "passthroughBehavior": "when_no_match",
				  "httpMethod": "ANY",
				  "cacheNamespace": "irx7tm",
				  "cacheKeyParameters": [
					"method.request.path.proxy"
				  ],
				  "type": "http_proxy"
				}
			  }
			}
		  }
		}
		'''
		template = template.replace('{{url}}',url)
		template = template.replace('{{title}}',title)
		template = template.replace('{{version_date}}',version_date)

		return str.encode(template)


	def create_api(self, url):
		if not url:
			self.error('Please provide a valid URL end-point')

		print(f'Creating => {url}...')

		template = self.get_template()
		response = self.client.import_rest_api(
			parameters={
				'endpointConfigurationTypes':'REGIONAL'
			},
			body=template
		)
		resource_id, proxy_url = self.create_deployment(response['id'])
		self.store_api(
			response['id'],
			response['name'],
			response['createdDate'],
			response['version'],
			url,
			resource_id,
			proxy_url
		)


	def update_api(self, api_id, url):
		if not any([api_id, url]):
			self.error('Please provide a valid API ID and URL end-point')

		if url[-1] == '/':
			url = url[:-1]

		resource_id = self.get_resource(api_id)
		if resource_id:
			print(f'Found resource {resource_id} for {api_id}!')
			response = self.client.update_integration(
				restApiId=api_id,
				resourceId=resource_id,
				httpMethod='ANY',
				patchOperations=[
					{
						'op': 'replace',
						'path': '/uri',
						'value': '{}/{}'.format(url,r'{proxy}'),
					},
				]
			)
			return response['uri'].replace('/{proxy}','') == url
		else:
			self.error(f'Unable to update, no valid resource for {api_id}')


	def delete_api(self, api_id):
		if not api_id:
			self.error('Please provide a valid API ID')
		items = self.list_api()
		for item in items:
			item_api_id = item['id']
			if item_api_id == api_id:
				response = self.client.delete_rest_api(
					restApiId=api_id
				)
				return True
		return False


	def list_api(self):
		response = self.client.get_rest_apis()
		for item in response['items']:
			created_dt = item['createdDate']
			api_id = item['id']
			name = item['name']
			proxy_url = self.get_integration(api_id).replace('{proxy}','')
			url = f'https://{api_id}.execute-api.us-east-1.amazonaws.com/fireprox/'
			print(f'[{created_dt}] ({api_id}) {name}: {url} => {proxy_url}')
		return response['items']


	def store_api(self, api_id, name, created_dt, version_dt, url,
		resource_id, proxy_url):
		print(
			f'[{created_dt}] ({api_id}) {name} => {proxy_url} ({url})'
		)


	def create_deployment(self, api_id):
		if not api_id:
			self.error('Please provide a valid API ID')

		response = self.client.create_deployment(
			restApiId=api_id,
			stageName='fireprox',
			stageDescription='FireProx Prod',
			description='FireProx Production Deployment'
		)
		resource_id = response['id']
		return (resource_id,
			f'https://{api_id}.execute-api.us-east-1.amazonaws.com/fireprox/')


	def get_resource(self, api_id):
		if not api_id:
			self.error('Please provide a valid API ID')
		response = self.client.get_resources(restApiId=api_id)
		items = response['items']
		for item in items:
			item_id = item['id']
			item_path = item['path']
			if item_path == '/{proxy+}':
				return item_id
		return None


	def get_integration(self, api_id):
		if not api_id:
			self.error('Please provide a valid API ID')
		resource_id = self.get_resource(api_id)
		response = self.client.get_integration(
			restApiId=api_id,
			resourceId=resource_id,
			httpMethod='ANY'
		)
		return response['uri']


parser = argparse.ArgumentParser(description='FireProx API Gateway Manager')
parser.add_argument('--access_key',
	help='AWS Access Key', type=str, default=None)
parser.add_argument('--secret_access_key',
	help='AWS Secret Access Key', type=str, default=None)
parser.add_argument('--command',
	help='Commands: list, create, delete, update', type=str, default=None)
parser.add_argument('--api_id',
	help='API ID', type=str, required=False)
parser.add_argument('--url',
	help='URL end-point', type=str, required=False)
args = parser.parse_args()

fp = FireProx(args)


def main():

	#print(fp.get_resource(fp.api_id))
	#sys.exit(1)

	if args.command == 'list':
		print(f'Listing API\'s...')
		result = fp.list_api()

	elif args.command == 'create':
		result = fp.create_api(fp.url)

	elif args.command == 'delete':
		result = fp.delete_api(fp.api_id)
		success = 'Success!' if result else 'Failed!'
		print(f'Deleting {fp.api_id} => {success}')

	elif args.command == 'update':
		print(f'Updating {fp.api_id} => {fp.url}...')
		result = fp.update_api(fp.api_id,fp.url)
		success = 'Success!' if result else 'Failed!'
		print(f'API Update Complete: {success}')
	

if __name__ == '__main__':
	main()


