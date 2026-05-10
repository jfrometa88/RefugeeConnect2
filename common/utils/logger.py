import logging
from pathlib import Path

def setup_logger(name:str) -> logging.Logger:
    """Configurar el sistema de logging"""
    
    log_dir = Path("common") / "data" / "logs"

    log_dir.mkdir(parents=True, exist_ok=True)
    
    log_filename = log_dir / "logs.log"
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_filename, encoding='utf-8'),
            logging.StreamHandler()  # también muestra en consola
        ]
    )    
    return logging.getLogger(name)

