#!/usr/bin/python
import json
import subprocess
import tempfile
from ansible.module_utils.basic import AnsibleModule

as_user = ""
as_pwdfile = ""

def asadmin(asadmin_args):
    args = ["/home/aleksi/servers/payara41/bin/asadmin",
            "--user", as_user,
            "--passwordfile", as_pwdfile] + asadmin_args;

    p = subprocess.Popen(args, stdout=subprocess.PIPE)
    out, err = p.communicate()

    lines = out.split("\n")
    if not lines[-1]:
        del lines[-1]

    status_line = lines[-1]
    ok = "executed successfully" in status_line

    return {"ok": ok, "stdout": out, "stdout_lines": lines}

def create_password_file(password):
    file = tempfile.NamedTemporaryFile(delete=False);
    file.write("AS_ADMIN_PASSWORD="+password)
    file.close()
    return file.name

def parse_domain_status(stdout):
    domains = {}
    for line in stdout[:-1]:
        name, status = line.split(" ", 1)
        running = "not running" not in status
        restart_required = "restart" in status
        domains[name] =({"running": running, "restart_required": restart_required})
    return domains

def domain_status():
    rs = asadmin(["list-domains"])
    if rs["ok"]:
        rs["domains"] = parse_domain_status(rs["stdout_lines"]);
    return rs

def create_domain(name):
    rs = asadmin(["create-domain", name])
    if rs["ok"]:
        rs = domain_status()
    return rs;

def delete_domain(name):
    rs = asadmin(["delete-domain", name])
    return rs;

def exit_with_status(module, rs):
    name = module.params["name"]
    if rs["ok"] and name in rs["domains"].keys():
        module.exit_json(changed=True, status=rs["domains"][name])
    elif rs["ok"]:
        module.fail_json(msg="Domain '" + name + "' not created.")
    else:
        module.fail_json(msg=rs.stdout)

def exit_without_status(module, rs):
    if rs["ok"]:
        module.exit_json(changed=True)
    else:
        module.fail_json(msg=rs.stdout)

def main():
    module = AnsibleModule(
        argument_spec = dict(
            state     = dict(default='present', choices=['present', 'absent']),
            name      = dict(required=True),
            user      = dict(default='admin'),
            password  = dict(default='', no_log=True)
            )
    )

    global as_user
    global as_pwdfile

    as_user = module.params["user"]
    as_pwdfile = create_password_file(module.params["password"])

    name = module.params["name"]
    state = module.params["state"]
    rs = domain_status()
    domain_present = name in rs["domains"].keys()

    if rs["ok"]:
        if state == "present":
            if domain_present:
                module.exit_json(changed=False, status=rs["domains"][name])
            else:
                exit_with_status(module, create_domain(name))
        elif state == "absent":
            if not domain_present:
                module.exit_json(changed=False)
            else:
                exit_without_status(module, delete_domain(name))
    else:
        module.fail_json(msg=rs.stdout)

if __name__ == '__main__':
    main()
