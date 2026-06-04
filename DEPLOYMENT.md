# Deployment Manual: Running the APC Validation App on T-Cloud Public

This guide walks you through deploying this Streamlit app to **T-Cloud Public**
(Deutsche Telekom's public cloud) from scratch. It is written for someone new to
cloud computing, so it explains the concepts as it goes. Follow it top to bottom.

By the end you will have the app running on a public address that colleagues can
reach in their browser.

---

## 1. The big picture (read this first)

You are going to do three things:

1. **Build a container image** of the app and store it in a cloud **registry**.
2. **Create a cluster** (a managed group of servers) to run containers.
3. **Deploy the image** onto the cluster and **expose it** so people can open it.

A few terms in plain language:

| Term | What it means |
|------|---------------|
| **Container image** | A frozen, self-contained snapshot of the app plus everything it needs to run. Built from the `Dockerfile` in this repo. |
| **Registry (SWR)** | A private storage for container images in the cloud. T-Cloud's is called **SWR** (Software Repository for Container). |
| **Cluster (CCE)** | A managed set of servers that run your containers using Kubernetes. T-Cloud's is **CCE** (Cloud Container Engine). |
| **Node** | One worker server inside the cluster. Your container actually runs on a node. |
| **Workload / Deployment** | The instruction that says "run this image, this many copies." |
| **Pod** | A running instance of your container on a node. |
| **Service / Load Balancer (ELB)** | The front door that gives your app a network address and sends visitors to the pod. |

> **Why containers?** The image runs the same way everywhere, so you do not need
> Python, Streamlit, or anything else installed on the cloud servers or your own
> laptop. You also never need to install Docker locally for this process.

---

## 2. Prerequisites

- Access to the **T-Cloud Public console** with permission to use SWR and CCE.
- This GitHub repository.
- A web browser. That is all. **No local Docker is required.**

---

## 3. Build the image and push it to SWR

The image is built automatically by **GitHub Actions** (a free build service that
runs on GitHub's servers) and pushed into SWR. You never build it on your laptop.

### 3a. Create an SWR organization

1. In the T-Cloud console, open **SWR (Software Repository for Container)**.
2. Click **Create Organization**. An organization is just a namespace that holds
   your images. Give it a name (example: `it_innovation`).

### 3b. Get your SWR login details

1. In SWR, click **Generate Login Command**.
2. It shows a `docker login` line containing a **username** (looks like
   `eu-de@AK...`), a **password** (a long login key), and the **registry host**
   (example: `swr.eu-de.otc.t-systems.com`). Copy all three.
   - Prefer the **long-term** login option if offered; the temporary one expires
     in 24 hours.

### 3c. Tell GitHub the SWR details

In GitHub: **Settings -> Secrets and variables -> Actions**, add:

| Type | Name | Value |
|------|------|-------|
| Secret | `SWR_USERNAME` | the username from the login command |
| Secret | `SWR_PASSWORD` | the password/login key |
| Variable | `SWR_REGISTRY` | the host, e.g. `swr.eu-de.otc.t-systems.com` |
| Variable | `SWR_ORGANIZATION` | the organization name you created |

> Secrets are encrypted and hidden; variables are plain text. Credentials go in
> secrets.

### 3d. Run the build

The workflow `.github/workflows/build-push-swr.yml` runs automatically on every
push to `main`, or you can trigger it manually from the **Actions** tab
(**Build and Push to SWR -> Run workflow**).

When it finishes green, your image is in SWR at:

```
<SWR_REGISTRY>/<SWR_ORGANIZATION>/comparisonapp:latest
```

Confirm it appears in the SWR console under your organization.

---

## 4. Create the cluster (CCE)

1. In the T-Cloud console, open **CCE (Cloud Container Engine)** and click
   **Create Cluster**.
2. **Configure Cluster:**
   - **Type:** `CCE Standard Cluster` (simpler and cheaper than Turbo).
   - **Cluster Name:** e.g. `comparisonapp-cluster`.
   - **Enterprise Project:** pick the project your team uses for billing/access.
   - **Cluster Version:** the recommended default is fine.
   - **Cluster Scale:** smallest option (`Nodes: 50`). This only sizes the
     management layer; you will run just one worker node.
   - **Master Nodes:** `Single` for a non-critical internal tool (cheaper), or
     `3 (HA)` for resilience. **This cannot be changed later.**
3. **Network Settings:**
   - **VPC:** select an existing private network, or **Create VPC** and accept
     defaults. **Cannot be changed later.**
   - **IPv6:** off.
   - **Security groups:** `Auto generate`.
   - Leave the container network model and service CIDR at their defaults.
4. **Select Add-ons:** keep the defaults (Container Network, Storage, CoreDNS).
   **Turn off "Cloud Native Cluster Monitoring"** (the Prometheus stack); it is
   heavy and unnecessary for one small app. Log Collection and Node Problem
   Detector are fine to keep.
5. **Configure Add-on:** for Log Collection, leave `Container logs` and
   `Kubernetes Events` checked; leave audit/control-plane logs unchecked.
6. **Confirm Settings** and create. This takes several minutes. Wait for the
   cluster status to show **Running**.

---

## 5. Add a worker node

A new cluster has **no servers to run containers on yet**. You must add one.

1. In your cluster, go to **Nodes -> Node Pools**.
2. If a node pool exists but shows `Nodes (Actual/Desired): 0 / 0`, click
   **Resize** and set the node count to **1**. (Creating a node pool only defines
   a template; it launches no servers until you set a count above zero.)
   - If no pool exists, click **Create Node Pool** first.
3. Node settings:
   - **Billing:** Pay-per-use (easiest to start).
   - **Specifications:** `4 vCPU / 8 GB` is comfortable for this app.
   - **Login mode:** set a key pair or password (required, even if you never use it).
   - **EIP / public IP:** **No / skip**. The node does not need its own public
     address; visitors arrive through the load balancer instead.
   - **Network settings:** keep the default VPC/subnet and the **auto-generated
     security group**. Do **not** restrict the NodePort range (30000-32767); the
     load balancer needs it. You may safely restrict **SSH (port 22)** to your own
     IP, or remove it.
4. Wait until **Nodes** shows one node in **Running** state.

---

## 6. Deploy the app (create a workload)

1. In the cluster, go to **Workloads -> Deployments -> Create Workload**.
2. **Basic Info:**
   - **Workload Type:** `Deployment`.
   - **Workload Name:** `comparisonapp`.
   - **Namespace:** `default`.
   - **Pods:** `1` (this app keeps user data in memory per session and should not
     be scaled to multiple copies).
3. **Container Settings -> Basic Info:**
   - **Image Name:** select `comparisonapp` from SWR.
   - **Image Tag:** select `latest` (required).
   - **CPU Quota:** Request `0.25`, Limit `1` core.
   - **Memory Quota:** Request `512`, Limit `2048` MiB. (Lower limits risk the app
     being killed when processing large CSV uploads.)
   - **Pull Policy:** tick **Always** (so redeploys pull the newest `latest`).
   - Leave Privileged off, Init Container off.
4. **Container Settings -> Health Check:** add both probes pointing at the app's
   health endpoint:
   - **Liveness Probe:** HTTP, path `/_stcore/health`, port `8501`.
   - **Readiness Probe:** HTTP, path `/_stcore/health`, port `8501`.
   - The load balancer only sends traffic to pods that pass the readiness check.
5. **Image Access Credential:** see the important note in Section 7 before
   finishing; you will likely need a custom pull secret.
6. **Service Settings:** see Section 8 to add the front door.
7. Leave **Advanced Settings** at their defaults.

---

## 7. Image pull credential (important, common error)

When CCE tries to download your image from SWR, it must authenticate. The built-in
`default-secret` sometimes fails with a **`401 Unauthorized`** error (often when
SWR and CCE are in different projects). If your pod shows
`ErrImagePull ... 401 Unauthorized`, do this:

1. Go to **ConfigMaps and Secrets -> Secrets -> Create Secret**.
2. Fill in:
   - **Name:** `swr-pull-secret`
   - **Namespace:** `default`
   - **Secret Type:** `kubernetes.io/dockerconfigjson` (the "image pull secret" type)
   - **Repository Address:** your registry host, e.g. `swr.eu-de.otc.t-systems.com`
   - **Username:** your SWR username (`eu-de@AK...`, same as `SWR_USERNAME`)
   - **Password:** your SWR login key (same as `SWR_PASSWORD`)
3. On the `comparisonapp` deployment, click **Upgrade**, open the container's
   **Basic Info**, and set **Image Access Credential** to **`swr-pull-secret`**.
   Save. The pod will retry and pull successfully.

> Alternative: set the SWR repository to **Public** (then no credential is needed),
> but only if the image contains nothing sensitive and your policy allows it.

---

## 8. Expose the app (Service / Load Balancer)

This gives the app a public address.

1. In **Service Settings** (during workload creation) or under **Services and
   Ingresses** afterwards, click **+ / Create Service**.
2. Settings:
   - **Service Name:** `comparisonapp`.
   - **Service Type:** **LoadBalancer**.
   - **Service Affinity:** Cluster-level.
   - **Load Balancer:** `Shared`, `Auto create`. Give it a name.
   - **EIP:** **Auto assign** (this is what makes the app reachable from the
     internet). Choose a small bandwidth (1-5 Mbit/s). Choose `Do not use` only if
     you will access it privately through a corporate network connected to the VPC.
   - **Health Check:** Global/TCP defaults are fine.
3. **Port mapping (get this right, it is the most common mistake):**
   - **Container Port = `8501`** (the port the app listens on inside the container).
   - **Service Port = `80`** (the port people use in the browser).
   - **Protocol:** TCP.
   - Rule of thumb: **Container Port = where the app listens (8501); Service Port =
     how you reach it (80).** Reversing these makes the backend "Unhealthy" and
     nothing loads.
4. **Access Control (optional whitelist):** to restrict who can reach the app, set
   **Whitelist** and add your public IP as `<your-IP>/32` (find it at ifconfig.me).
   Set to **All IP addresses** to allow everyone. You can change this any time.
5. Save / create the workload.

---

## 9. Open the app

1. Go to **Services and Ingresses** and find the `comparisonapp` service.
2. Note the **ELB Public IP** (ignore the Cluster IP and Private IP).
3. Open `http://<ELB-Public-IP>` in your browser. You should see the
   "APC Validation" page with three tabs.
4. Quick functional test: in **Daily Matching**, upload one Left (Temptation) CSV
   and one Right (APC) CSV and confirm the match panel populates. This proves the
   full pipeline runs inside the container, not just that the page loads.

---

## 10. Give it a domain name (optional)

To replace the raw IP with something like `apc-validation.nexperia.com`:

1. **Reserve the EIP** so it never changes. In the **EIP** console confirm the
   address is held/bound. If you recreate the service later, reuse this same EIP
   rather than auto-assigning a new one.
2. **Create a DNS record:**
   - For a Nexperia domain: ask IT to add an **A record**
     `apc-validation.nexperia.com -> <ELB-Public-IP>`.
   - For a domain hosted in T-Cloud **DNS**: create a public hosted zone and add an
     **A record** for the subdomain pointing at the ELB IP.
3. **Widen access** if others need it: set the listener **Access Control** to your
   colleagues' IP range or to **All IP addresses**.
4. **For HTTPS (recommended when sharing):** upload a certificate to the cloud
   **Certificate Manager**, add an **HTTPS listener on 443** to the ELB using that
   cert, forwarding to container port 8501. Make sure **WebSocket** support is
   enabled on the listener, because Streamlit relies on websockets.

---

## 11. Updating the app later

1. Push your code change to `main`. GitHub Actions rebuilds the image and pushes a
   new `latest` to SWR.
2. In CCE, open the `comparisonapp` deployment and click **Redeploy / Restart**
   (or **Upgrade**). Because Pull Policy is `Always`, it pulls the new image.

> Cleaner long-term practice: deploy by the **commit-SHA tag** (also pushed by the
> workflow) instead of `latest`, so every running version is explicit and you can
> roll back to a known image.

---

## 12. Troubleshooting (issues you may actually hit)

| Symptom | Likely cause | Fix |
|---------|--------------|-----|
| Pod stuck **Not ready**, log says `ErrImagePull ... 401 Unauthorized` | CCE cannot authenticate to SWR with `default-secret` | Create `swr-pull-secret` and attach it (Section 7) |
| Workload won't schedule: "no node is available" | Node pool has 0 nodes | Resize the node pool to 1 (Section 5) |
| Page does not load; ELB **backend Unhealthy** | Port mapping reversed (Service Port and Container Port swapped) | Set Container Port `8501`, Service Port `80` (Section 8) |
| Page times out (hangs) | IP whitelist is blocking you, or your public IP changed | Re-check your IP at ifconfig.me and update the whitelist, or set Access Control to allow all (Section 8) |
| "Connection refused" quickly | Wrong access port, or nothing serving | Confirm the listener frontend port and that the backend is Healthy |
| Backend Unhealthy after a correct port mapping | Node security group blocks the NodePort range | Restore the default inbound rule for ports 30000-32767 |
| Pod restarts during a large upload | Memory limit too low | Raise the memory limit (e.g. 2048 -> 4096 MiB) |

---

## Appendix: files in this repo that support deployment

- `Dockerfile` - builds the container image (Streamlit on port 8501, with a
  `/_stcore/health` health endpoint).
- `.dockerignore` - keeps unnecessary files out of the image.
- `.streamlit/config.toml` - headless mode, telemetry off, 500 MB upload limit.
- `.github/workflows/build-push-swr.yml` - builds and pushes the image to SWR.
- `k8s/deployment.yaml` - a portable Kubernetes manifest (alternative to clicking
  through the CCE console; edit the `image:` line and apply with `kubectl`).
- `docker-compose.yml` - for running the container locally if you ever have a
  container tool installed.
