import json
import logging
import os
import shutil
import sys
import zipfile
from pathlib import Path
import httpx

logger = logging.getLogger("impcon.updater")

CURRENT_VERSION = "1.0.0"

# URL padrão para checagem de atualizações (pode ser sobrescrito por variável de ambiente)
DEFAULT_UPDATE_URL = os.environ.get(
    "IMPCON_UPDATE_URL",
    "https://raw.githubusercontent.com/postrenan/ImpCon/main/build/updates/version.json"
)

def parse_version(ver_str: str) -> tuple[int, ...]:
    """Converte string de versão '1.2.3' em tupla comparável (1, 2, 3)."""
    clean = ver_str.strip().lstrip("v")
    parts = []
    for p in clean.split("."):
        try:
            parts.append(int(p))
        except ValueError:
            parts.append(0)
    return tuple(parts)

async def check_for_updates(update_url: str = DEFAULT_UPDATE_URL) -> dict:
    """
    Consulta o manifesto de versão remoto.
    Retorna dados sobre a disponibilidade de atualização.
    """
    try:
        async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
            resp = await client.get(update_url)
            if resp.status_code != 200:
                return {
                    "ok": False,
                    "update_available": False,
                    "current_version": CURRENT_VERSION,
                    "error": f"Servidor de atualização respondeu com HTTP {resp.status_code}",
                }
            
            data = resp.json()
            latest_ver = data.get("version", CURRENT_VERSION)
            download_url = data.get("download_url", "")
            changelog = data.get("changelog", "Melhorias gerais e correções de bugs.")
            
            is_newer = parse_version(latest_ver) > parse_version(CURRENT_VERSION)
            
            return {
                "ok": True,
                "update_available": is_newer,
                "current_version": CURRENT_VERSION,
                "latest_version": latest_ver,
                "download_url": download_url,
                "changelog": changelog,
            }
    except Exception as e:
        logger.warning(f"Não foi possível verificar atualizações em {update_url}: {e}")
        return {
            "ok": False,
            "update_available": False,
            "current_version": CURRENT_VERSION,
            "error": str(e),
        }

async def apply_update(download_url: str, target_dir: Path) -> dict:
    """
    Baixa o pacote ZIP de atualização (~200KB) e substitui com segurança
    apenas os arquivos de código (app.py, modules/, static/).
    """
    if not download_url:
        return {"ok": False, "error": "URL de download não informada."}

    temp_zip = target_dir / "temp" / "update.zip"
    temp_extract = target_dir / "temp" / "update_extracted"
    
    try:
        logger.info(f"Baixando pacote de atualização de {download_url}...")
        async with httpx.AsyncClient(timeout=60.0, follow_redirects=True) as client:
            resp = await client.get(download_url)
            resp.raise_for_status()
            temp_zip.write_bytes(resp.content)

        logger.info(f"Download concluído ({len(resp.content):,} bytes). Extraindo...")
        
        if temp_extract.exists():
            shutil.rmtree(temp_extract)
        temp_extract.mkdir(parents=True, exist_ok=True)

        with zipfile.ZipFile(temp_zip, 'r') as zip_ref:
            zip_ref.extractall(temp_extract)

        # Se o zip contém uma subpasta interna (ex: ImpCon-main ou update/), localiza a raiz
        root_source = temp_extract
        contents = list(temp_extract.iterdir())
        if len(contents) == 1 and contents[0].is_dir():
            root_source = contents[0]

        # Arquivos e pastas permitidos para sobrescrever no aplicativo
        allowed_items = ["app.py", "modules", "static", "requirements.txt"]

        updated_files = []
        for item_name in allowed_items:
            src_item = root_source / item_name
            dst_item = target_dir / item_name
            
            if src_item.exists():
                if src_item.is_dir():
                    if dst_item.exists():
                        shutil.rmtree(dst_item)
                    shutil.copytree(src_item, dst_item)
                else:
                    shutil.copy2(src_item, dst_item)
                updated_files.append(item_name)

        # Limpeza do zip e arquivos temporários de atualização
        if temp_zip.exists():
            temp_zip.unlink()
        if temp_extract.exists():
            shutil.rmtree(temp_extract)

        logger.info(f"Atualização aplicada com sucesso! Itens atualizados: {', '.join(updated_files)}")
        return {
            "ok": True,
            "message": "Atualização instalada com sucesso! Reinicie o aplicativo ou recarregue a página.",
            "updated_items": updated_files,
        }

    except Exception as e:
        logger.exception(f"Erro ao aplicar atualização remota: {e}")
        if temp_zip.exists():
            try: temp_zip.unlink()
            except Exception: pass
        if temp_extract.exists():
            try: shutil.rmtree(temp_extract)
            except Exception: pass
        return {"ok": False, "error": f"Falha na atualização: {e}"}
