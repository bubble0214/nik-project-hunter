import urllib.request
# Try to directly fetch the detail.js
try:
    r = urllib.request.urlopen('http://www.cfcpn.com/static/assets/js/cfcpn2021/list/detail.js', timeout=10)
    print(r.read().decode('utf-8')[:3000])
except Exception as e:
    print(f'Error: {e}')