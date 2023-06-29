import json
import urllib.request

endpoint="http://ip-api.com/batch"
ips = [{"query": "208.80.152.201", "fields": "country"}, "8.8.8.8"]
params = json.dumps(ips).encode('utf8')
req = urllib.request.Request(endpoint, data=params,
                             headers={'content-type': 'application/json'})
response = urllib.request.urlopen(req)

response = urllib.request.urlopen(req)
print(response.read().decode('utf8'))
