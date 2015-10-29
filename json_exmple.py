import json
data = {
	'name':'yogesh',
	'company' :'Aditi',
	'salary' : 5.7
}
json_str = json.dumps(data)
print type(json_str)

json_dict = json.loads(json_str)
print type(json_dict)