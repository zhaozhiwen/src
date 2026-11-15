"""Unsupported integrated JSON output fails before publishing any data."""
import json
from pathlib import Path
import subprocess
import sys
import os
import tempfile

for argument in sys.argv[2:]:
    if argument.startswith("--plugin-path="):
        os.environ["GEMC_PLUGIN_PATH"] = argument.split("=", 1)[1]

binary=str(Path(sys.argv[1]).resolve());source=Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory() as directory:
    work=Path(directory)
    database=work/'geometry.db'
    setup=subprocess.run([sys.executable,str(source/'examples/basic/b1/b1.py'),'-f','sqlite','-sql',str(database)],cwd=work,capture_output=True,text=True)
    assert setup.returncode==0,setup.stdout+setup.stderr
    good=subprocess.run([binary,'-n=2','-nthreads=1','-gparticle=[{name: geantino, p: 1*GeV}]','-gstreamer=[{format: json, filename: events}]'],cwd=work,capture_output=True,text=True)
    assert good.returncode==0,good.stdout+good.stderr
    for formats in ['{format: json, filename: dose}','{format: csv, filename: csvdose}, {format: json, filename: dose}']:
        case=work/('mixed' if formats.startswith('{format: csv') else 'run');case.mkdir()
        bad=subprocess.run([binary,str(source/'examples/basic/b1/b1.yaml'),'-sql='+str(database),'-n=10','-nthreads=1','-gstreamer=['+formats+']'],cwd=case,capture_output=True,text=True)
        assert bad.returncode!=0, 'Integrated JSON unexpectedly succeeded with an empty measurement'
        message=(bad.stdout+bad.stderr).lower()
        assert 'json' in message and 'run' in message and 'support' in message,message
        assert not list(case.glob('dose*.json')),list(case.iterdir())
    for format in ['csv','ascii']+(['root'] if '--root' in sys.argv[3:] else []):
        workcase=work/('supported_'+format);workcase.mkdir()
        positive=subprocess.run([binary,str(source/'examples/basic/b1/b1.yaml'),'-sql='+str(database),'-n=10','-nthreads=1','-gparticle=[{name: proton, p: 1*GeV, vz: -10*cm}]','-gstreamer=[{format: '+format+', filename: dose}]'],cwd=workcase,capture_output=True,text=True)
        assert positive.returncode==0,positive.stdout+positive.stderr
        target=workcase/('dose_digitized.csv' if format=='csv' else 'dose.'+('root' if format=='root' else 'txt'))
        assert target.exists() and target.stat().st_size>0,(format,list(workcase.iterdir()))
    for argument in sys.argv[2:]:
        if argument.startswith('--frame-driver='):
            driver=argument.split('=',1)[1]
            frame=subprocess.run([driver,'-gstreamer=[{format: json, filename: frame}]'],cwd=work,capture_output=True,text=True)
            assert frame.returncode==0,frame.stdout+frame.stderr
            document=json.loads((work/'frame.json').read_text())
            assert document['frames'][0]['header']['frame_id']==7,document
            assert document['frames'][0]['payload']==[[1,2,3,4,5]],document
print('Event/frame JSON and supported run backends pass; integrated/mixed JSON fails before output.')
