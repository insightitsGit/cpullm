"""Prepare/verify the retrieval encoder cache; no model training or DB needed."""
from pathlib import Path
import argparse
import json
import os

MODEL = 'sentence-transformers/all-mpnet-base-v2'

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cache-root',type=Path,required=True,help='HF_HOME directory to populate or verify')
    parser.add_argument('--offline-check',action='store_true',help='Forbid network connections and load only cached assets')
    parser.add_argument('--receipt',type=Path,help='Optional JSON verification receipt')
    args=parser.parse_args()
    root=args.cache_root.resolve()
    os.environ['HF_HOME']=str(root)
    os.environ['HF_HUB_CACHE']=str(root/'hub')
    if args.offline_check:
        os.environ['HF_HUB_OFFLINE']='1'
        os.environ['TRANSFORMERS_OFFLINE']='1'
        import socket
        def denied(*a,**k):raise RuntimeError('Network connection attempted during offline encoder verification')
        socket.socket.connect=denied
        socket.create_connection=denied
    elif os.environ.get('HF_HUB_OFFLINE')=='1' or os.environ.get('TRANSFORMERS_OFFLINE')=='1':
        parser.error('Unset offline flags while preparing downloads, or use --offline-check')
    try:
        # Match the library's required import order on Windows.
        import pyarrow  # noqa: F401
        from sentence_transformers import SentenceTransformer
        encoder=SentenceTransformer(MODEL,device='cpu',cache_folder=str(root/'hub'),local_files_only=args.offline_check)
        vector=encoder.encode(['CPU LLM encoder cache verification.'],convert_to_numpy=True)
        if vector.shape!=(1,768):raise RuntimeError('Unexpected encoder dimensions')
        from huggingface_hub import try_to_load_from_cache
        config=try_to_load_from_cache(MODEL,'config.json',cache_dir=str(root/'hub'))
        snapshot=Path(config).parent.name if isinstance(config,str) else None
    except Exception as exc:
        if args.offline_check:
            parser.exit(2,'Offline encoder cache unavailable or incompatible. Prepare this cache on a connected machine first; no model training is needed. ('+type(exc).__name__+')\n')
        raise
    receipt=dict(model=MODEL,cache_root=str(root),cached_snapshot=snapshot,
        offline_check=args.offline_check,network_connections_forbidden=args.offline_check,
        dimensions=768,training=False)
    if args.receipt:
        args.receipt.parent.mkdir(parents=True,exist_ok=True)
        args.receipt.write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(receipt,indent=2))

if __name__=='__main__':main()
