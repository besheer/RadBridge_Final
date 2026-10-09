"""Restrict managed VPN clients to HTTPS/HTTP and the tunnel DNS resolver."""
import subprocess
import sys

CHAIN='RBWG-INPUT'
IFACE='wg-radbridge'

def run(*args,check=True):
    p=subprocess.run(['iptables','-w','10',*args],capture_output=True,text=True)
    if check and p.returncode:raise RuntimeError('Managed VPN firewall operation failed')
    return p.returncode

def up():
    if run('-S',CHAIN,check=False):run('-N',CHAIN)
    else:
        # This program owns only this exact chain; verify before flushing it.
        p=subprocess.check_output(['iptables','-S',CHAIN],text=True)
        for line in p.splitlines():
            if line.startswith('-A ') and 'RADBRIDGE_MANAGED_VPN' not in line:
                raise RuntimeError('Unexpected rule in owned VPN chain')
    run('-F',CHAIN)
    run('-A',CHAIN,'-m','conntrack','--ctstate','ESTABLISHED,RELATED','-m','comment','--comment','RADBRIDGE_MANAGED_VPN','-j','ACCEPT')
    for proto,ports in [('tcp','53,80,443'),('udp','53')]:
        run('-A',CHAIN,'-p',proto,'-d','10.77.240.1','-m','multiport','--dports',ports,'-m','comment','--comment','RADBRIDGE_MANAGED_VPN','-j','ACCEPT')
    run('-A',CHAIN,'-m','comment','--comment','RADBRIDGE_MANAGED_VPN','-j','REJECT')
    if run('-C','INPUT','-i',IFACE,'-j',CHAIN,check=False):run('-I','INPUT','1','-i',IFACE,'-j',CHAIN)
    if run('-C','DOCKER-USER','-i',IFACE,'-m','comment','--comment','RADBRIDGE_MANAGED_VPN','-j','DROP',check=False):
        run('-I','DOCKER-USER','1','-i',IFACE,'-m','comment','--comment','RADBRIDGE_MANAGED_VPN','-j','DROP')
    # No routed Internet or lateral access, even before Docker's accept rules.
    if run('-C','FORWARD','-i',IFACE,'-m','comment','--comment','RADBRIDGE_MANAGED_VPN','-j','DROP',check=False):
        run('-I','FORWARD','1','-i',IFACE,'-m','comment','--comment','RADBRIDGE_MANAGED_VPN','-j','DROP')

def down():
    for parent,rule in [('INPUT',['-i',IFACE,'-j',CHAIN]),('DOCKER-USER',['-i',IFACE,'-m','comment','--comment','RADBRIDGE_MANAGED_VPN','-j','DROP']),('FORWARD',['-i',IFACE,'-m','comment','--comment','RADBRIDGE_MANAGED_VPN','-j','DROP'])]:
        if run('-C',parent,*rule,check=False)==0:run('-D',parent,*rule)
    if run('-S',CHAIN,check=False)==0:
        p=subprocess.check_output(['iptables','-S',CHAIN],text=True)
        assert all('RADBRIDGE_MANAGED_VPN' in x for x in p.splitlines() if x.startswith('-A '))
        run('-F',CHAIN);run('-X',CHAIN)

if __name__=='__main__':
    assert len(sys.argv)==2 and sys.argv[1] in ('up','down')
    up() if sys.argv[1]=='up' else down()
