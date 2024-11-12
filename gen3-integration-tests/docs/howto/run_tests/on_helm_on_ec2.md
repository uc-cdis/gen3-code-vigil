We can run tests locally against a Gen3 instance running on an EC2 machine with helm as follows:

#### 1. Update SSH configuration, add a host like
```
Host ec2_helm
  User <ec2-user>
  Hostname <ec2-host>
  ProxyJump <jumpbox-host>
  IdentityFile <path-to-id-file-authorized-on-ec2-host>
```
_**Note**: ProxyJump is optional, to be added if a jump box is needed to connect to the EC2 host_

#### 2. Copy over kubernetes configuration
Copy over the contents of `~/.kube/config` to the local file. There are 3 sections here - cluster, context and user.
Note down the port used by the server (found in the cluster block)

_**Tip**: you can use [kubectx](https://github.com/ahmetb/kubectx) to manage multiple kubernetes clusters_


#### 3. Copy over the id files from .ssh to /var/root/.ssh
Sudo makes the ssh look for certificates in /var/root/.ssh

#### 4. Forward ports while connecting to the EC2 machine
sudo ssh -L <kube-config-port>:localhost:<kube-config-port> -L 443:localhost:443 -L 80:localhost:80 -L 6443:localhost:6443 -F <path-to-ssh-config> ec2_helm

_**Note**: sudo is needed to forward 80 and 443, and sudo sets the commands to run from root (not HOME), so the path to ssh config is needed_
