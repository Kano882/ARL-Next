#!/usr/bin/env python3
"""GeoIP 数据库按需获取与校验（fetch_geoip.py）。

三个库文件（约 88MB）不再随仓库分发，部署时装入 Docker 命名卷 arl_geoip。
策略见 backend/GeoLite2/GEOIP_VERSIONS.json：
- ip2region_v4.xdb：公网直链（代理镜像优先）+ sha256 强校验。
- GeoLite2-*.mmdb：需 MaxMind 许可，仅当 MAXMIND_LICENSE_KEY 非空时下载；
  无 key 时跳过（服务降级运行，不中断扫描）。

Usage:
    python3 tools/fetch_geoip.py --dir ./geoip_out
    python3 tools/fetch_geoip.py --dir ./geoip_out --maxmind-key <key>
    MAXMIND_LICENSE_KEY=<key> python3 tools/fetch_geoip.py --dir ./geoip_out

退出码：ip2region 缺失/校验失败时 exit 1；GeoLite2 无 key 跳过时 exit 0。
"""
import argparse
import hashlib
import json
import os
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VERSIONS_FILE = ROOT / "backend" / "GeoLite2" / "GEOIP_VERSIONS.json"

MAXMIND_EDITIONS = {
    "GeoLite2-City.mmdb": "GeoLite2-City",
    "GeoLite2-ASN.mmdb": "GeoLite2-ASN",
}


def sha256_of(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def download(url, dest, timeout=120):
    req = urllib.request.Request(url, headers={"User-Agent": "ARL-Next-geoip/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as r, open(dest, "wb") as f:
        while True:
            chunk = r.read(1 << 20)
            if not chunk:
                break
            f.write(chunk)


def fetch_ip2region(meta, dest_dir):
    name = "ip2region_v4.xdb"
    dest = dest_dir / name
    if dest.is_file() and sha256_of(dest) == meta["sha256"]:
        print(f"OK: {name} 已存在且校验通过，跳过下载")
        return True
    urls = [meta.get("url"), meta.get("mirror")]
    for url in [u for u in urls if u]:
        try:
            print(f"下载 {name} <- {url}")
            download(url, dest)
        except Exception as e:
            print(f"WARN: {url} 下载失败: {e}")
            continue
        digest = sha256_of(dest)
        if digest == meta["sha256"]:
            print(f"OK: {name} 校验通过")
            return True
        print(f"WARN: {name} 校验失败（期望 {meta['sha256'][:16]}…，实际 {digest[:16]}…），尝试下一源")
        dest.unlink(missing_ok=True)
    print(f"FAIL: {name} 所有下载源均失败")
    return False


def fetch_maxmind(name, meta, dest_dir, license_key):
    dest = dest_dir / name
    if dest.is_file() and sha256_of(dest) == meta["sha256"]:
        print(f"OK: {name} 已存在且校验通过，跳过下载")
        return True
    if not license_key:
        print(f"SKIP: {name} 需 MaxMind 许可（MAXMIND_LICENSE_KEY 为空），跳过；服务以降级模式运行")
        return True
    edition = MAXMIND_EDITIONS[name]
    url = (f"https://download.maxmind.com/app/geoip_download"
           f"?edition_id={edition}&license_key={license_key}&suffix=tar.gz")
    tmp = dest_dir / f"{name}.tar.gz"
    try:
        print(f"下载 {name}（{edition}）")
        download(url, tmp)
    except Exception as e:
        print(f"WARN: {name} 下载失败: {e}")
        return True  # 降级：不阻断部署
    import tarfile
    try:
        with tarfile.open(tmp) as tf:
            member = next((m for m in tf.getmembers() if m.name.endswith(name)), None)
            if member is None:
                print(f"WARN: {name} 压缩包内未找到目标文件，跳过")
                return True
            member.name = name
            tf.extract(member, dest_dir)
    except Exception as e:
        print(f"WARN: {name} 解包失败: {e}")
        return True
    finally:
        tmp.unlink(missing_ok=True)
    if dest.is_file() and sha256_of(dest) == meta["sha256"]:
        print(f"OK: {name} 校验通过")
    else:
        print(f"WARN: {name} 校验与基线不一致（版本已更新），保留下载文件；请核对 GEOIP_VERSIONS.json")
    return True


def main():
    ap = argparse.ArgumentParser(description="GeoIP 数据库按需获取与校验")
    ap.add_argument("--dir", required=True, help="输出目录（将挂载为命名卷内容）")
    ap.add_argument("--maxmind-key", default="", help="MaxMind license key（也可走环境变量）")
    args = ap.parse_args()

    try:
        versions = json.loads(VERSIONS_FILE.read_text())
    except (OSError, ValueError) as e:
        print(f"FAIL: 版本声明读取失败: {e}")
        return 1

    dest_dir = Path(args.dir)
    dest_dir.mkdir(parents=True, exist_ok=True)
    license_key = args.maxmind_key or os.environ.get("MAXMIND_LICENSE_KEY", "")

    ok = fetch_ip2region(versions["ip2region_v4.xdb"], dest_dir)
    for name in ("GeoLite2-City.mmdb", "GeoLite2-ASN.mmdb"):
        fetch_maxmind(name, versions[name], dest_dir, license_key)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
