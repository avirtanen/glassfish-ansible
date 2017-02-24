#!/usr/bin/python
import json
import subprocess
import tempfile
import os
import re
from ansible.module_utils.basic import AnsibleModule

as_user = ""
as_pwdfile = ""

def asadmin(asadmin_args):
    args = ["/home/aleksi/servers/payara41/bin/asadmin",
            "--user", as_user,
            "--passwordfile", as_pwdfile] + asadmin_args;

    p = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    out, err = p.communicate()

    lines = out.split("\n")
    if not lines[-1]:
        del lines[-1]

    status_line = lines[-1]
    ok = "executed successfully" in status_line

    return {"ok": ok, "stdout": out, "stdout_lines": lines, "error": err}

def create_password_file(password):
    file = tempfile.NamedTemporaryFile(delete=False);
    file.write("AS_ADMIN_PASSWORD="+password)
    file.close()
    return file.name

def parse_applications_status(stdout):
    applications = {}
    if stdout[0] == "Nothing to list.":
        return applications

    for line in stdout[1:-1]:
        name, app_type, status = re.sub(" +", " ", line.strip()).split(" ")
        applications[name] =({"type": app_type, "status": status})

    return applications

def list_applications():
    rs = asadmin(["list-applications", "--long"])
    if rs["ok"]:
        rs["applications"] = parse_applications_status(rs["stdout_lines"]);
    return rs

def application_status(name):
    rs = list_applications();
    if rs["ok"] and name in rs["applications"]:
        return {"ok": True, name: rs["applications"][name]}
    elif rs["ok"]:
        return {"ok": True}
    else:
        return rs

def deploy_application(name, war):
    rs = asadmin([
            "deploy",
            "--name", name,
            war])
    if rs["ok"]:
        rs = application_status(name)
    return rs;

def redeploy_application(name, war):
    rs = asadmin([
            "redeploy",
            "--name", name,
            war])
    if rs["ok"]:
        rs = application_status(name)
    return rs;

def undeploy_application(name):
    rs = asadmin(["undeploy", name])
    if rs["ok"]:
        rs = application_status(name)
    return rs;

def exit_with_status(module, rs):
    name = module.params["name"]
    if rs["ok"] and name in rs.keys():
        module.exit_json(changed=True, status=rs[name])
    elif rs["ok"]:
        module.fail_json(msg="Application '" + name + "' not deployed.")
    else:
        module.fail_json(msg=rs["stdout"], error=rs["error"])

def exit_without_status(module, rs):
    if rs["ok"]:
        module.exit_json(changed=True)
    else:
        module.fail_json(msg=rs["stdout"], error=rs["error"])

def main():
    module = AnsibleModule(
        argument_spec = dict(
            state     = dict(default='present', choices=['present', 'absent']),
            name      = dict(required=True),
            war       = dict(),
            target    = dict(),
            redeploy  = dict(default=False),
            user      = dict(default='admin'),
            password  = dict(default='', no_log=True)
            )
    )

    global as_user
    global as_pwdfile

    try:
        as_user = module.params["user"]
        as_pwdfile = create_password_file(module.params["password"])

        state = module.params["state"]
        name = module.params["name"]
        war = module.params["war"]
        redeploy = module.params["redeploy"] == "True"

        rs = application_status(name)
        if rs["ok"]:
            app_present = name in rs.keys()
            if state == "present":
                if app_present and not redeploy:
                    module.exit_json(changed=False, status=rs[name])
                elif app_present:
                    exit_with_status(module, redeploy_application(name, war))
                else:
                    exit_with_status(module, deploy_application(name, war))
            elif state == "absent":
                if not app_present:
                    module.exit_json(changed=False)
                else:
                    exit_without_status(module, undeploy_application(name))
        else:
            module.fail_json(msg=rs["stdout"], error=rs["error"])
    finally:
        os.remove(as_pwdfile)

if __name__ == '__main__':
    main()
