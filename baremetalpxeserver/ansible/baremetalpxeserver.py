#!/usr/bin/env python
# encoding: utf-8
import argparse
from zstacklib import *
import os

# create log
logger_dir = "/var/log/zstack/"
create_log(logger_dir)
banner("Starting to deploy baremetal pxeserver agent")
start_time = datetime.now()
# set default value
file_root = "files/baremetalpxeserver"
pip_url = "https=//pypi.python.org/simple/"
proxy = ""
sproxy = ""
zstack_repo = 'false'
post_url = ""
chrony_servers = None
pkg_baremetalpxeserver = ""
virtualenv_version = "12.1.1"
remote_user = "root"
remote_pass = None
remote_port = None

# get parameter from shell
parser = argparse.ArgumentParser(description='Deploy baremetal pxeserver agent to host')
parser.add_argument('-i', type=str, help="""specify inventory host file
                        default=/etc/ansible/hosts""")
parser.add_argument('--private-key', type=str, help='use this file to authenticate the connection')
parser.add_argument('-e', type=str, help='set additional variables as key=value or YAML/JSON')

args = parser.parse_args()
argument_dict = eval(args.e)

# update the variable from shell arguments
locals().update(argument_dict)
virtenv_path = "%s/virtualenv/baremetalpxeserver/" % zstack_root
baremetalpxeserver_root = "%s/baremetalpxeserver/package" % zstack_root
host_post_info = HostPostInfo()
host_post_info.host_inventory = args.i
host_post_info.host = host
host_post_info.post_url = post_url
host_post_info.chrony_servers = chrony_servers
host_post_info.private_key = args.private_key
host_post_info.remote_user = remote_user
host_post_info.remote_pass = remote_pass
host_post_info.remote_port = remote_port
if remote_pass is not None and remote_user != 'root':
    host_post_info.become = True

# include zstacklib.py
(distro, distro_version, distro_release, _) = get_remote_host_info(host_post_info)
zstacklib_args = ZstackLibArgs()
zstacklib_args.distro = distro
zstacklib_args.distro_release = distro_release
zstacklib_args.distro_version = distro_version
zstacklib_args.zstack_repo = zstack_repo
zstacklib_args.yum_server = yum_server
zstacklib_args.zstack_root = zstack_root
zstacklib_args.host_post_info = host_post_info
zstacklib_args.pip_url = pip_url
zstacklib_args.trusted_host = trusted_host
zstacklib = ZstackLib(zstacklib_args)

# name: judge this process is init install or upgrade
if file_dir_exist("path=" + baremetalpxeserver_root, host_post_info):
    init_install = False
else:
    init_install = True
    # name: create root directories
    command = 'mkdir -p %s %s' % (baremetalpxeserver_root, virtenv_path)
    run_remote_command(command, host_post_info)

run_remote_command("rm -rf %s/*" % baremetalpxeserver_root, host_post_info)
# name: install virtualenv
virtual_env_status = check_and_install_virtual_env(virtualenv_version, trusted_host, pip_url, host_post_info)
if virtual_env_status is False:
    command = "rm -rf %s && rm -rf %s" % (virtenv_path, baremetalpxeserver_root)
    run_remote_command(command, host_post_info)
    sys.exit(1)

# name: make sure virtualenv has been setup
# here change "rm -rf virtualenv" to "-f %s/bin/python" till zstack 2.0 due to a bug exist in old version, we need to
# make sure all users upgrade to new version
command = "rm -rf %s && virtualenv --system-site-packages %s " % (virtenv_path, virtenv_path)
run_remote_command(command, host_post_info)

# name: install dependencies
if distro in RPM_BASED_OS:
    if zstack_repo != 'false':
        command = ("pkg_list=`rpm -q dnsmasq nginx syslinux vsftpd nmap | grep \"not installed\" | awk '{ print $2 }'` && for pkg in $pkg_list; do yum --disablerepo=* --enablerepo=%s install -y $pkg; done;") % zstack_repo
        run_remote_command(command, host_post_info)
    else:
        for pkg in ["dnsmasq", "nginx", "vsftpd", "syslinux", "nmap"]:
            yum_install_package(pkg, host_post_info)
    command = "(which firewalld && systemctl stop firewalld && systemctl enable firewalld) || true"
    run_remote_command(command, host_post_info)
    set_selinux("state=disabled", host_post_info)

elif distro in DEB_BASED_OS:
    install_pkg_list = ["dnsmasq", "vsftpd", "syslinux", "nginx", "nmap"]
    apt_install_packages(install_pkg_list, host_post_info)
    command = "(chmod 0644 /boot/vmlinuz*) || true"
else:
    error("unsupported OS!")

# name: check and mount /opt/zstack-dvd
command = """
[ -f /opt/zstack-dvd/GPL ] || exit 1;
mkdir -p /var/lib/zstack/baremetal/{dnsmasq,ftp/{ks,zstack-dvd,scripts},tftpboot/{zstack,pxelinux.cfg},vsftpd} /var/log/zstack/baremetal/;
cp -f /usr/share/syslinux/pxelinux.0 /var/lib/zstack/baremetal/tftpboot/;
umount /var/lib/zstack/baremetal/ftp/zstack-dvd/ || true;
mount --bind /opt/zstack-dvd /var/lib/zstack/baremetal/ftp/zstack-dvd/
cp -f /opt/zstack-dvd/images/pxeboot/{vmlinuz,initrd.img} /var/lib/zstack/baremetal/tftpboot/zstack/;
"""
run_remote_command(command, host_post_info)

# name: config iptables
command = """
sed -i 's/IPTABLES_MODULES=""/IPTABLES_MODULES="nf_conntrack_ftp"/g' /etc/sysconfig/iptables-config;
/sbin/iptables-save | grep -w -q 67 || iptables -I INPUT -p udp -m state --state NEW --sport 67:68 --dport 67:68 -j ACCEPT;
/sbin/iptables-save | grep -w -q 69 || iptables -I INPUT -p udp -m state --state NEW --dport 69 -j ACCEPT;
/sbin/iptables-save | grep -q "dport 21" || iptables -I INPUT -p tcp -m state --state NEW --dport 21 -j ACCEPT;
/sbin/iptables-save | grep -q "dport 6080" || iptables -I INPUT -p tcp -m tcp --dport 6080 -j ACCEPT;
/sbin/iptables-save | grep -q "dport 7770" || iptables -I INPUT -p tcp -m tcp --dport 7770 -j ACCEPT;
/sbin/iptables-save | grep -q "dport 7771" || iptables -I INPUT -p tcp -m tcp --dport 7771 -j ACCEPT;
/sbin/iptables-save | grep -q "dport 7772" || iptables -I INPUT -p tcp -m tcp --dport 7772 -j ACCEPT;
/sbin/service iptables save;
/sbin/service iptables restart
"""
run_remote_command(command, host_post_info)

# name: copy zstacklib
copy_arg = CopyArg()
copy_arg.src = "files/zstacklib/%s" % pkg_zstacklib
copy_arg.dest = "%s/%s" % (baremetalpxeserver_root, pkg_zstacklib)
copy_zstacklib = copy(copy_arg, host_post_info)

if copy_zstacklib != "changed:False":
    agent_install_arg = AgentInstallArg(trusted_host, pip_url, virtenv_path, init_install)
    agent_install_arg.agent_name = "zstacklib"
    agent_install_arg.agent_root = baremetalpxeserver_root
    agent_install_arg.pkg_name = pkg_zstacklib
    agent_install(agent_install_arg, host_post_info)

# name: copy baremetal pxeserver agent
copy_arg = CopyArg()
copy_arg.src = "%s/%s" % (file_root, pkg_baremetalpxeserver)
copy_arg.dest = "%s/%s" % (baremetalpxeserver_root, pkg_baremetalpxeserver)
copy_baremetalpxeserver = copy(copy_arg, host_post_info)

if copy_baremetalpxeserver != "changed:False":
    agent_install_arg = AgentInstallArg(trusted_host, pip_url, virtenv_path, init_install)
    agent_install_arg.agent_name = "baremetalpxeserver"
    agent_install_arg.agent_root = baremetalpxeserver_root
    agent_install_arg.pkg_name = pkg_baremetalpxeserver
    agent_install(agent_install_arg, host_post_info)

# name: copy service file
# only support centos redhat debian and ubuntu
copy_arg = CopyArg()
copy_arg.src = "%s/zstack-baremetalpxeserver" % file_root
copy_arg.dest = "/etc/init.d/"
copy_arg.args = "mode=755"
copy(copy_arg, host_post_info)

# name: copy shellinaboxd
VSFTPD_ROOT_PATH = "/var/lib/zstack/baremetal/ftp"
copy_arg = CopyArg()
copy_arg.src = "%s/shellinaboxd" % file_root
copy_arg.dest = VSFTPD_ROOT_PATH
copy(copy_arg, host_post_info)

# name: copy noVNC.tar.gz
copy_arg = CopyArg()
copy_arg.src = "%s/noVNC.tar.gz" % file_root
copy_arg.dest = "/var/lib/zstack/baremetal/"
copy(copy_arg, host_post_info)

# name: restart baremetalpxeserveragent
if distro in RPM_BASED_OS:
    command = "service zstack-baremetalpxeserver stop && service zstack-baremetalpxeserver start && chkconfig zstack-baremetalpxeserver on"
elif distro in DEB_BASED_OS:
    command = "update-rc.d zstack-baremetalpxeserver start 97 3 4 5 . stop 3 0 1 2 6 . && service zstack-baremetalpxeserver stop && service zstack-baremetalpxeserver start"
run_remote_command(command, host_post_info)

host_post_info.start_time = start_time
handle_ansible_info("SUCC: Deploy baremetal pxeserver agent successful", host_post_info, "INFO")

sys.exit(0)
