"""Re-ingest ten existing abstracts (same content) one by one, then as one folder; print seconds."""
import json, pathlib, shutil, sys, tempfile, time
from cpu_llm.pipeline import Appliance
def main():
    names = json.loads(pathlib.Path(sys.argv[2]).read_text())
    files = [pathlib.Path('/home/user/cpullm/tests/fixtures/quantum_computing') / f'{v["name"]}.md'
             for v in names.values() if v.get('used') == 'abstract only'][:10]
    folder_mode = len(sys.argv) > 3
    with Appliance(namespace=sys.argv[1]) as app:
        app.ingest(files[0])
        t = time.perf_counter()
        for f in files:
            app.ingest(f)
        each = time.perf_counter() - t
        out = dict(per_document_each=round(each / len(files), 2))
        if folder_mode:
            with tempfile.TemporaryDirectory() as d:
                for f in files:
                    shutil.copy(f, d)
                t = time.perf_counter(); app.ingest(d, consolidate='end')
                out['per_document_folder_end'] = round((time.perf_counter() - t) / len(files), 2)
        print(json.dumps(out))
if __name__ == '__main__':
    main()
