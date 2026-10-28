# SPDX-License-Identifier: GPL-3.0-only
"""Current stable ISO metadata from distribution-owned HTTPS endpoints."""
import datetime
import json
import re
from pathlib import Path
from urllib.parse import urljoin, urlsplit
from core import RES, SUPPORT, url_opener

SOURCES={
    'Ubuntu':'https://releases.ubuntu.com/',
    'Debian':'https://cdimage.debian.org/debian-cd/current-live/amd64/iso-hybrid/',
    'Fedora':'https://fedoraproject.org/releases.json'
}

def fetch(url):
    with url_opener().open(url,timeout=20) as response:
        data=response.read(4*1024*1024+1)
    if len(data)>4*1024*1024:raise ValueError('Release metadata exceeds its size limit')
    return data.decode('utf-8')

def checksums(text):
    return [(match[1].lower(),match[2]) for match in re.finditer(r'^([0-9a-fA-F]{64})\s+\*?([^\r\n]+)$',text,re.M)]

def version(text):return tuple(int(n) for n in re.findall(r'\d+',text))

def row(provider,name,filename,url,digest,features,method='extract'):
    if not re.fullmatch(r'[0-9a-fA-F]{64}',digest) or urlsplit(url).scheme!='https':raise ValueError('Invalid official image metadata')
    return {'id':'current-'+provider.lower()+'-'+filename,'provider':provider,'name':name,'filename':filename,'sha256':digest.lower(),'mirrors':[url],'download_page':SOURCES[provider] if provider!='Fedora' else 'https://fedoraproject.org/workstation/download','distribution':provider.lower(),'supported_features':features,'install_method':method,'architecture':'x86_64'}

def ubuntu():
    base=SOURCES['Ubuntu'];today=datetime.date.today()
    streams=sorted(set(re.findall(r'href="(\d{2}\.\d{2}(?:\.\d+)*)/"',fetch(base))),key=version)
    streams=[s for s in streams if (2000+int(s[:2]),int(s[3:5]))<=(today.year,today.month)]
    channels={s[:5]:s for s in streams}
    lts=[s for channel,s in channels.items() if channel.endswith('.04') and int(channel[:2])%2==0][-2:]
    chosen=list(dict.fromkeys([streams[-1]]+list(reversed(lts))))
    records=[]
    for stream in chosen:
        page=urljoin(base,stream+'/')
        images=[(digest,name) for digest,name in checksums(fetch(page+'SHA256SUMS')) if re.fullmatch(r'ubuntu-[\d.]+-desktop-amd64\.iso',name)]
        if not images:continue
        digest,name=max(images,key=lambda pair:version(pair[1].split("-desktop-")[0]))
        number=name.removeprefix('ubuntu-').removesuffix('-desktop-amd64.iso')
        records.append(row('Ubuntu','Ubuntu '+number+(' LTS' if stream in lts else '')+' Desktop',name,page+name,digest,'','raw'))
    return records

def debian():
    base=SOURCES['Debian'];records=[]
    for digest,name in checksums(fetch(base+'SHA256SUMS')):
        found=re.fullmatch(r'debian-live-([\d.]+)-amd64-(standard|gnome|kde|xfce|cinnamon|mate|lxde|lxqt)\.iso',name)
        if found:records.append(row('Debian','Debian '+found[1]+' Live '+found[2].upper(),name,base+name,digest,'debian-persistence,syslinux6'))
    return sorted(records,key=lambda item:(not 'XFCE' in item['name'],item['name']))

def fedora():
    data=json.loads(fetch(SOURCES['Fedora']))
    stable=[item for item in data if str(item.get('version','')).isdigit() and item.get('arch')=='x86_64' and item.get('subvariant') in ('Workstation','KDE') and item.get('link','').endswith('.iso')]
    latest=max(int(item['version']) for item in stable);records=[]
    for item in stable:
        if int(item['version'])!=latest:continue
        url=item['link'];records.append(row('Fedora','Fedora '+str(latest)+' '+item['subvariant'],Path(urlsplit(url).path).name,url,item['sha256'],'','raw'))
    return records

def current_catalog():
    for path in [SUPPORT/'current_releases.json',RES/'settings/current_releases.json']:
        try:
            value=json.loads(path.read_text())
            assert value['rows'] and len(value['rows'])<=100
            for item in value['rows']:
                assert re.fullmatch('[0-9a-f]{64}',item['sha256']) and all(urlsplit(u).scheme=='https' for u in item['mirrors'])
            return value
        except (OSError,ValueError,KeyError,TypeError,AssertionError):continue
    return {'rows':[],'updated':'','errors':{}}

def refresh(progress=None):
    previous=current_catalog();records=[];errors={}
    for number,(provider,loader) in enumerate([('Ubuntu',ubuntu),('Debian',debian),('Fedora',fedora)]):
        if progress:progress(number/3,'Checking current '+provider+' releases')
        try:
            found=loader()
            if not found:raise ValueError('The official source returned no stable x86_64 images')
            records.extend(found)
        except Exception as error:
            errors[provider]=str(error)
            records.extend(item for item in previous['rows'] if item.get('provider')==provider)
    if not records:raise ValueError('Cannot refresh the official release catalog. '+str(errors))
    value={'updated':datetime.datetime.now(datetime.timezone.utc).isoformat(),'rows':records,'errors':errors,'sources':SOURCES}
    SUPPORT.mkdir(parents=True,exist_ok=True)
    path=SUPPORT/'current_releases.json';temporary=path.with_suffix('.tmp');temporary.write_text(json.dumps(value,indent=2));temporary.replace(path)
    return value
