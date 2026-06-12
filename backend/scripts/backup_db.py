"""
数据库定时备份与恢复工具脚本。

支持 SQLite 及 PostgreSQL。
运行方式：
  备份：python backend/scripts/backup_db.py backup
  恢复：python backend/scripts/backup_db.py restore <备份文件路径>
"""

import os
import sys
import gzip
import shutil
import subprocess
import re
import logging
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

# 将 backend 目录挂载到 PATH 方便导入配置
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

try:
    from app.core.config import get_settings
except ImportError:
    logger.warning("警告: 无法从 app.core.config 导入配置，将退回到读取环境变量。")
    class FallbackSettings:
        database_url = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///dev.db")
    def get_settings():
        return FallbackSettings()


BACKUP_DIR = Path(__file__).resolve().parent.parent / "data" / "backups"
MAX_BACKUPS = 7


def setup_backup_dir() -> None:
    """初始化备份文件夹。"""
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)


def get_db_params(url: str) -> dict:
    """从数据库连接串中解析类型和必要连接参数。"""
    # 净化连接串协议前缀便于 urlparse 提取
    clean_url = re.sub(r'\+(aiosqlite|asyncpg|psycopg2|aiomysql)', '', url)
    res = urlparse(clean_url)
    
    db_type = res.scheme
    if "sqlite" in db_type:
        # 兼容 sqlite:///dev.db 及绝对路径
        db_path = url.split("///")[-1]
        # 如果是相对路径，相对于 backend 目录
        absolute_path = Path(__file__).resolve().parent.parent / db_path
        return {"type": "sqlite", "path": absolute_path}
    elif "postgresql" in db_type or "postgres" in db_type:
        return {
            "type": "postgresql",
            "host": res.hostname or "localhost",
            "port": res.port or 5432,
            "username": res.username or "postgres",
            "password": res.password or "",
            "database": res.path.lstrip("/"),
        }
    else:
        raise ValueError(f"不支持的数据库类型: {db_type}")


def run_backup() -> None:
    """执行备份主逻辑。"""
    setup_backup_dir()
    settings = get_settings()
    url = settings.database_url
    
    logger.info("[%s] 开始数据库备份...", datetime.now().isoformat())
    try:
        params = get_db_params(url)
    except Exception as exc:
        logger.error("解析数据库参数失败: %s", exc)
        sys.exit(1)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    if params["type"] == "sqlite":
        source_path = params["path"]
        if not source_path.exists():
            logger.error("SQLite 数据库文件未找到: %s", source_path)
            sys.exit(1)
            
        backup_filename = f"backup_sqlite_{timestamp}.db.gz"
        backup_path = BACKUP_DIR / backup_filename
        
        logger.info("正在压缩并备份 SQLite 数据: %s -> %s", source_path, backup_path)
        try:
            with open(source_path, "rb") as f_in:
                with gzip.open(backup_path, "wb") as f_out:
                    shutil.copyfileobj(f_in, f_out)
            logger.info("SQLite 备份成功。")
        except Exception as exc:
            logger.error("压缩 SQLite 文件失败: %s", exc)
            sys.exit(1)
            
    elif params["type"] == "postgresql":
        backup_filename = f"backup_postgres_{timestamp}.sql.gz"
        backup_path = BACKUP_DIR / backup_filename
        
        logger.info("正在备份 PostgreSQL 数据库: %s -> %s", params["database"], backup_path)
        
        # 组装 pg_dump 命令行，用 PGPASSWORD 避免明文密码交互
        env = os.environ.copy()
        if params["password"]:
            env["PGPASSWORD"] = params["password"]
            
        cmd = [
            "pg_dump",
            "-h", str(params["host"]),
            "-p", str(params["port"]),
            "-U", params["username"],
            "-d", params["database"],
            "-F", "p" # 纯文本 SQL 模式，更方便跨平台查看与恢复
        ]
        
        try:
            # 运行 pg_dump 并将其输出重定向到 gzip 压缩包中
            process = subprocess.Popen(cmd, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            stdout, stderr = process.communicate()
            
            if process.returncode != 0:
                logger.error("pg_dump 执行失败: %s", stderr.decode("utf-8", errors="ignore"))
                sys.exit(1)
                
            with gzip.open(backup_path, "wb") as f_out:
                f_out.write(stdout)
                
            logger.info("PostgreSQL 备份成功。")
        except Exception as exc:
            logger.error("执行 pg_dump 失败: %s，请检查系统是否已安装 PostgreSQL 命令行工具。", exc)
            sys.exit(1)

    # 清理超期备份文件
    rotate_backups()


def rotate_backups() -> None:
    """清理多余的历史备份文件（仅保留最近 MAX_BACKUPS 次）。"""
    all_backups = sorted(
        [f for f in BACKUP_DIR.glob("backup_*.*.gz")],
        key=os.path.getmtime
    )
    if len(all_backups) > MAX_BACKUPS:
        excess = len(all_backups) - MAX_BACKUPS
        logger.info("备份文件总数（%d）已超过上限（%d），正在清理最近 %d 个最老的备份...", len(all_backups), MAX_BACKUPS, excess)
        for old_file in all_backups[:excess]:
            try:
                old_file.unlink()
                logger.info("已删除旧备份: %s", old_file.name)
            except Exception as exc:
                logger.error("删除文件 %s 失败: %s", old_file, exc)


def run_restore(backup_file: str) -> None:
    """从备份文件恢复数据库主逻辑。"""
    backup_path = Path(backup_file)
    if not backup_path.exists():
        # 如果是相对备份目录的文件名
        backup_path = BACKUP_DIR / backup_file
        if not backup_path.exists():
            logger.error("备份文件未找到: %s", backup_file)
            sys.exit(1)
            
    settings = get_settings()
    url = settings.database_url
    
    logger.info("[%s] 开始从备份文件恢复数据库...", datetime.now().isoformat())
    try:
        params = get_db_params(url)
    except Exception as exc:
        logger.error("解析目标数据库参数失败: %s", exc)
        sys.exit(1)

    if params["type"] == "sqlite":
        target_path = params["path"]
        logger.info("正在恢复 SQLite 数据: %s -> %s", backup_path, target_path)
        
        # 确保目标路径的目录存在
        target_path.parent.mkdir(parents=True, exist_ok=True)
        
        # 备份当前数据库以防灾难
        if target_path.exists():
            temp_backup = target_path.with_suffix(".db.bak")
            logger.info("备份当前活动库至临时文件 %s", temp_backup)
            shutil.copy2(target_path, temp_backup)
            
        try:
            with gzip.open(backup_path, "rb") as f_in:
                with open(target_path, "wb") as f_out:
                    shutil.copyfileobj(f_in, f_out)
            logger.info("SQLite 数据恢复成功。")
            if target_path.with_suffix(".db.bak").exists():
                target_path.with_suffix(".db.bak").unlink()
        except Exception as exc:
            logger.error("解压或写入 SQLite 文件失败: %s", exc)
            if target_path.with_suffix(".db.bak").exists():
                logger.info("正在还原之前备份的活动库...")
                shutil.copy2(target_path.with_suffix(".db.bak"), target_path)
            sys.exit(1)
            
    elif params["type"] == "postgresql":
        logger.info("正在恢复 PostgreSQL 数据库: %s -> %s", backup_path, params["database"])
        
        # 解压 SQL 内容
        try:
            with gzip.open(backup_path, "rb") as f_in:
                sql_content = f_in.read()
        except Exception as exc:
            logger.error("解压备份文件失败: %s", exc)
            sys.exit(1)
            
        # 准备 psql 命令行
        env = os.environ.copy()
        if params["password"]:
            env["PGPASSWORD"] = params["password"]
            
        cmd = [
            "psql",
            "-h", str(params["host"]),
            "-p", str(params["port"]),
            "-U", params["username"],
            "-d", params["database"]
        ]
        
        try:
            # 运行 psql，写入解压后的 SQL
            process = subprocess.Popen(cmd, env=env, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            stdout, stderr = process.communicate(input=sql_content)
            
            if process.returncode != 0:
                logger.error("psql 执行失败: %s", stderr.decode("utf-8", errors="ignore"))
                sys.exit(1)
                
            logger.info("PostgreSQL 数据恢复成功。")
        except Exception as exc:
            logger.error("执行 psql 恢复失败: %s，请检查系统是否已安装 PostgreSQL 客户端。", exc)
            sys.exit(1)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        logger.info("用法: python backup_db.py [backup|restore] [restore_file_path]")
        sys.exit(1)
        
    action = sys.argv[1].lower()
    if action == "backup":
        run_backup()
    elif action == "restore":
        if len(sys.argv) < 3:
            logger.error("错误: 恢复模式必须指定备份文件的路径或文件名。")
            sys.exit(1)
        run_restore(sys.argv[2])
    else:
        logger.error("未知的动作: %s。支持: backup, restore", action)
        sys.exit(1)
