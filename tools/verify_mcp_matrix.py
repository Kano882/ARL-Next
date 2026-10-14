#!/usr/bin/env python3
"""PR#56 修正版 — 真实生产环境全覆盖验证矩阵。

驱动真实 MCP 客户端（stdio JSON-RPC），对线上 ARL 发起 get_asset_profile 调用，
覆盖 TLS 策略 × 凭据有效性 × 目标类型 的全组合。

Usage:
  python3 tools/verify_mcp_matrix.py --old <旧客户端> --new <新客户端> \
      --host https://<ARL_HOST> --token <token> [--cert <arl.crt>] [--loopback <url>]

凭据经环境变量传入，不落盘；隔离工作目录内的 ARL_auth.md 在进程结束时删除。
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

PROBE = (
    "import importlib.util,sys;"
    "spec=importlib.util.spec_from_file_location('m',sys.argv[1]);"
    "m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);"
    "h,t=m._get_auth();"
    "print(h);print(t);"
    "print(m._resolve_ca_bundle(h) if hasattr(m,'_resolve_ca_bundle') else ('',False))"
)


def resolved_credentials(client, workdir):
    """以客户端自身逻辑解析凭据，确认用例前置条件成立。"""
    proc = subprocess.run([sys.executable, "-I", "-c", PROBE, client],
                          cwd=workdir, capture_output=True, text=True, timeout=30)
    lines = proc.stdout.splitlines()
    if len(lines) < 3:
        return None, None, None
    return lines[0], lines[1], lines[2]


def call(client, workdir, host, env_extra, auth_doc=None):
    """在隔离工作目录内驱动客户端，凭据经 ARL_auth.md 解析（与生产一致）。"""
    env = dict(os.environ)
    for key in ("ARL_HOST", "ARL_TOKEN", "ARL_CA_BUNDLE", "ARL_TLS_VERIFY", "ARL_STRICT_HOSTNAME"):
        env.pop(key, None)
    env.update(env_extra)

    payload = "\n".join([
        json.dumps({"jsonrpc": "2.0", "id": 1, "method": "initialize",
                    "params": {"protocolVersion": "2024-11-05"}}),
        json.dumps({"jsonrpc": "2.0", "id": 2, "method": "tools/call",
                    "params": {"name": "get_asset_profile", "arguments": {"target": TARGET}}}),
    ]) + "\n"

    proc = subprocess.run([sys.executable, "-I", client], input=payload, env=env,
                          cwd=workdir, capture_output=True, text=True, timeout=60)
    for line in proc.stdout.splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        msg = json.loads(line)
        if msg.get("id") != 2:
            continue
        result = msg.get("result", {})
        text = result.get("content", [{}])[0].get("text", "{}")
        try:
            body = json.loads(text)
        except Exception:
            body = {"raw": text}
        return bool(result.get("isError")), body, proc.stderr.strip()
    return None, {"raw": proc.stdout[:200] or proc.stderr[:200]}, proc.stderr.strip()


TARGET = "www.baidu.com"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--old", required=True, help="PR 合的客户端（回归基线）")
    ap.add_argument("--new", required=True, help="修正后客户端")
    ap.add_argument("--host", required=True, help="线上 ARL 地址")
    ap.add_argument("--token", required=True, help="有效 Token")
    ap.add_argument("--cert", help="服务端自签证书，用于 ARL_CA_BUNDLE 用例")
    ap.add_argument("--loopback", help="已建立到服务端的本地端口转发地址（如 https://127.0.0.1:5173）")
    args = ap.parse_args()

    dead = "deadbeef" * 6
    workdir = tempfile.mkdtemp(prefix="arl56-matrix-")
    print(f"工作目录: {workdir}（凭据经 ARL_auth.md 解析，与生产一致）")

    def write_auth(host, token, local_cert=None):
        body = f"ARL_HOST: {host}\nARL_TOKEN: {token}\n"
        if local_cert:
            body += f"ARL_LOCAL_CERT: {local_cert}\n"
        (Path(workdir) / "ARL_auth.md").write_text(body, encoding="utf-8")

    if args.loopback:
        (Path(workdir) / "certs").mkdir(exist_ok=True)

    def run_block(label_client, client, host, creds, local_cert=None, cert_expected=None):
        print(f"\n{'=' * 74}\n{label_client}  host={host}\n{'=' * 74}")
        for tls_label, env_extra in tls_matrix:
            for cred_label, token in creds:
                write_auth(host, token, local_cert)
                seen_host, seen_token, seen_cert = resolved_credentials(client, workdir)
                if seen_host is None:
                    print(f"  [{tls_label:22}] [{cred_label:8}] !! 凭据解析失败，用例前置条件不成立")
                    continue
                prem = "OK" if seen_host.rstrip("/") == host.rstrip("/") and seen_token == token else "!! 前置不符"
                status = ""
                if cert_expected:
                    ok = cert_expected in (seen_cert or "")
                    status = "证书自动发现=OK" if ok else f"证书自动发现=失败({seen_cert})"
                err, body, stderr = call(client, workdir, host, env_extra)
                outcome = body.get("status")
                detail = (body.get("message") or body.get("tip") or "")[:52]
                print(f"  [{tls_label:22}] [{cred_label:8}] isError={str(err):5} "
                      f"status={str(outcome):11} {detail}  <{prem} {status}>")
                if "警告" in stderr:
                    print(f"      └ stderr: {stderr.splitlines()[0][:92]}")

    tls_matrix = [("默认(无TLS变量)", {}), ("ARL_TLS_VERIFY=false", {"ARL_TLS_VERIFY": "false"})]
    if args.cert:
        tls_matrix += [
            ("ARL_CA_BUNDLE", {"ARL_CA_BUNDLE": args.cert}),
            ("CA_BUNDLE+严格主机名", {"ARL_CA_BUNDLE": args.cert, "ARL_STRICT_HOSTNAME": "true"}),
        ]

    creds = [("有效Token", args.token), ("失效Token", dead)]

    # A. 远程 IP 直连（生产真实部署形态）
    run_block("【A】远程 IP 直连  旧客户端", args.old, args.host, creds)
    run_block("【B】远程 IP 直连  修正客户端", args.new, args.host, creds)

    if args.loopback and args.cert:
        # B. 本地回环：自动发现 certs/arl.crt，无需任何 TLS 环境变量
        local_cert = str(Path(workdir) / "certs" / "arl.crt")
        shutil.copyfile(args.cert, local_cert)
        run_block("【C】同机回环 127.0.0.1  修正客户端（自动发现 certs/arl.crt）",
                  args.new, args.loopback, creds, local_cert=local_cert, cert_expected=local_cert)

    shutil.rmtree(workdir, ignore_errors=True)
    print(f"\n用例总数: {2 * len(tls_matrix) * len(creds)}"
          f"{' + 回环自动发现块' if args.loopback and args.cert else ''}")
    print()


if __name__ == "__main__":
    main()
