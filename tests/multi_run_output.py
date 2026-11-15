"""A second BeamOn preserves the first run, including backend header state."""
import csv
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

for argument in sys.argv[2:]:
    if argument.startswith("--plugin-path="):
        os.environ["GEMC_PLUGIN_PATH"] = argument.split("=", 1)[1]

binary=str(Path(sys.argv[1]).resolve())
with tempfile.TemporaryDirectory() as directory:
    for format in (['json','csv','ascii'] + (['root'] if '--root' in sys.argv[2:] else [])):
        work=Path(directory)/format;work.mkdir()
        (work/'runs.mac').write_text('/run/beamOn 3\n/run/beamOn 7\n')
        env=os.environ.copy();env['G4RUN_MANAGER_TYPE']='MT'
        result=subprocess.run([binary,'-nthreads=1','-geant4_macro='+str(work/'runs.mac'),'-gparticle=[{name: geantino, p: 1*GeV}]','-gstreamer=[{format: '+format+', filename: events}]'],cwd=work,env=env,capture_output=True,text=True)
        assert result.returncode==0,result.stdout+result.stderr
        if format=='json':
            counts=[len(json.loads(p.read_text())['events']) for p in work.glob('events*.json') if p.stat().st_size]
            assert sorted(counts)==[3,7],(format,counts)
        elif format=='csv':
            files=list(work.glob('events*_generated.csv'))
            counts=[len(list(csv.DictReader(p.open(),skipinitialspace=True))) for p in files]
            assert sorted(counts)==[3,7],(format,counts)
        else:
            suffix='root' if format=='root' else 'txt'
            files=list(work.glob('events*.'+suffix))
            assert len(files)==2,(format,[p.name for p in work.iterdir()])
            assert all(p.stat().st_size>0 for p in files),format
            if format=='ascii':
                assert sorted(p.read_text().count('Header Bank {') for p in files)==[3,7]
            else:
                counts=[]
                for file in files:
                    command='TFile f("'+file.name+'"); auto t=dynamic_cast<TTree*>(f.Get("event_header")); if(!t){gSystem->Exit(2);} std::cout<<"COUNT="<<t->GetEntries()<<std::endl; gSystem->Exit(0);'
                    check=subprocess.run(['root','-l','-b','-q','-e',command],cwd=work,capture_output=True,text=True,check=True)
                    import re
                    counts.append(int(re.search(r'COUNT=(\d+)',check.stdout)[1]))
                assert sorted(counts)==[3,7],counts
    work=Path(directory)/'multiple_workers_outputs';work.mkdir()
    (work/'runs.mac').write_text('/run/beamOn 3\n/run/beamOn 7\n')
    result=subprocess.run([binary,'-nthreads=2','-geant4_macro='+str(work/'runs.mac'),'-gparticle=[{name: geantino, p: 1*GeV}]','-gstreamer=[{format: json, filename: events}, {format: csv, filename: mirror}]'],cwd=work,capture_output=True,text=True)
    assert result.returncode==0,result.stdout+result.stderr
    for later,expected in [(False,3),(True,7)]:
        events=[e for p in work.glob('events*.json') if p.stat().st_size and ('_s2' in p.stem)==later for e in json.loads(p.read_text())['events']]
        assert sorted(e['header']['g4local_event'] for e in events)==list(range(expected)),events
        count=sum(len(list(csv.DictReader(p.open(),skipinitialspace=True))) for p in work.glob('mirror*_generated.csv') if ('_s2' in p.stem)==later)
        assert count==expected,(later,count)
    import re
    assert all(re.fullmatch(r'events_t\d+(_r\d+_s2)?',p.stem) for p in work.glob('events*.json'))
    work=Path(directory)/'integrated';work.mkdir()
    source=Path(__file__).resolve().parents[1];database=work/'geometry.db'
    setup=subprocess.run([sys.executable,str(source/'examples/basic/b1/b1.py'),'-f','sqlite','-sql',str(database)],cwd=work,capture_output=True,text=True)
    assert setup.returncode==0,setup.stdout+setup.stderr
    (work/'runs.mac').write_text('/run/beamOn 3\n/run/beamOn 7\n')
    result=subprocess.run([binary,str(source/'examples/basic/b1/b1.yaml'),'-sql='+str(database),'-nthreads=2','-seed=12345','-geant4_macro='+str(work/'runs.mac'),'-gparticle=[{name: proton, p: 1*GeV, vz: -10*cm}]','-gstreamer=[{format: csv, filename: dose}, {format: ascii, filename: mirror}]'],cwd=work,capture_output=True,text=True)
    assert result.returncode==0,result.stdout+result.stderr
    files=[p for p in work.glob('dose*_digitized.csv') if p.stat().st_size]
    assert len(files)==2 and (work/'dose_digitized.csv').exists(),[p.name for p in files]
    for path in files:
        rows=list(csv.DictReader(path.open(),skipinitialspace=True))
        assert len(rows)==1 and float(rows[0]['dose'])>0,(path,rows)
    assert len(list(work.glob('mirror*.txt')))>=2
    tags={re.search(r'_r\d+_s2',p.stem)[0] for p in work.iterdir() if re.search(r'_r\d+_s2',p.stem)}
    assert len(tags)==1,('Event and run outputs must share the master run tag',tags)
print('Repeated runs preserve event/run data across backends, workers, and multiple outputs.')
