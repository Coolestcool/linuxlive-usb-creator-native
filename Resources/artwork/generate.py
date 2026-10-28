#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-only
# Scalable artwork for the native edition, © 2026 Enrique (Coolestcool).
from pathlib import Path

OUT=Path(__file__).resolve().parent.parent/'img'
HEADER='<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}">'
def save(name,body,w=100,h=100):
    (OUT/(name+'.svg')).write_text(HEADER.format(w=w,h=h)+body+'</svg>')

def gradient(name,colors):
    return '<linearGradient id="'+name+'" x1="0" y1="0" x2="0" y2="1">'+''.join('<stop offset="%s%%" stop-color="%s"/>'%(100*i/(len(colors)-1),color) for i,color in enumerate(colors))+'</linearGradient>'

metal=gradient('metal',['#fff','#a9b3c1','#f3f5f7','#707c8f','#d9dfe9'])
blue=gradient('blue',['#c4f8ff','#33bcff','#0068b6','#163b7b'])
green=gradient('green',['#c7ff91','#57ef14','#169b00','#096000'])
disc='<defs>'+gradient('disc',['#fff','#ccd8d8','#edf1fb','#a5afb8','#f9ffff'])+'</defs><circle cx="50" cy="50" r="43" fill="url(#disc)" stroke="#727e85" stroke-width="2"/><path d="M50 10L43 39 17 31z" fill="#f7dce3" opacity=".65"/><path d="M73 81L57 60 83 56z" fill="#b4f2eb" opacity=".65"/><circle cx="50" cy="50" r="12" fill="#b6bfc4"/><circle cx="50" cy="50" r="6" fill="#11161a"/>'
usb='<defs>'+metal+'</defs><g transform="rotate(-25 50 50)"><path d="M34 4H66V24H34z" fill="#d5dde2" stroke="#5c6774" stroke-width="2"/><path d="M39 10H46V17H39zM54 10H61V17H54z" fill="#414a58"/><rect x="25" y="22" width="50" height="71" rx="12" fill="url(#metal)" stroke="#596879" stroke-width="2"/><path d="M50 74V39M50 49L39 43V36M50 60L61 53V45" fill="none" stroke="#1683cf" stroke-width="4"/><path d="M46 40L50 33 54 40" fill="#1683cf"/><circle cx="39" cy="34" r="3" fill="#1683cf"/><path d="M58 40H64V46H58z" fill="#1683cf"/><circle cx="50" cy="78" r="4" fill="#1683cf"/></g>'
pie='<defs>'+blue+green+'</defs><path d="M50 8A42 42 0 1 0 88 67L50 50z" fill="url(#blue)" stroke="#9ed6ff" stroke-width="2"/><path d="M57 54L96 44A40 40 0 0 1 72 92z" fill="url(#green)" stroke="#78ef44" stroke-width="2"/>'
save('cd',disc)
save('iso','<defs>'+metal+'</defs><path d="M15 3H65L85 23V97H15z" fill="url(#metal)" stroke="#7b8796" stroke-width="2"/><path d="M65 3V24H85" fill="#fff" stroke="#7b8796"/>'+ '<g transform="translate(12 30) scale(.72)">'+disc+'</g>')
save('download','<defs>'+metal+green+'</defs><path d="M11 64L22 52H78L89 64V92H11z" fill="url(#metal)" stroke="#566571" stroke-width="2"/><path d="M11 66H89M15 85H84" stroke="#6c7985"/><circle cx="78" cy="79" r="3" fill="#5eff18"/><path d="M38 4H62V44H82L50 73 18 44H38z" fill="url(#green)" stroke="#278a0c" stroke-width="2"/>')
save('usb',usb);save('persistence',pie)
save('refresh','<defs>'+blue+'</defs><path d="M81 32A35 35 0 0 0 22 25L12 16 9 50 44 45 33 34A21 21 0 0 1 68 37zM19 68A35 35 0 0 0 78 75L88 84 91 50 56 55 67 66A21 21 0 0 1 32 63z" fill="url(#blue)" stroke="#3ac8ff" stroke-width="2"/>')
save('launch','<g transform="scale(.5 1)"><defs>'+gradient('bolt',['#fffba0','#ffe100','#ff9e00','#fff6ab'])+'</defs><path d="M39 3H88L58 40H80L12 98 36 57H13z" fill="url(#bolt)" stroke="#ffb800" stroke-width="2"/></g>',w=50,h=100)
save('close','<defs>'+gradient('red',['#ffd1cc','#ff3629','#a60000'])+'</defs><path d="M17 6L50 38 83 6 96 19 63 50 96 81 83 95 50 62 17 95 4 81 37 50 4 19z" fill="url(#red)" stroke="#7d0b0b" stroke-width="2"/>')
save('min','<defs>'+gradient('red',['#ff8b84','#e22018','#8b0000'])+'</defs><rect x="7" y="43" width="86" height="19" rx="2" fill="url(#red)" stroke="#730e0b" stroke-width="2"/>')
save('back','<defs>'+blue+'</defs><path d="M45 10L5 50 45 90V66H94V34H45z" fill="url(#blue)" stroke="#58d2ff" stroke-width="2"/>')
save('help','<defs>'+metal+'</defs><circle cx="50" cy="50" r="44" fill="url(#metal)" stroke="#56616e" stroke-width="3"/><circle cx="50" cy="50" r="36" fill="#353c45"/><path d="M35 36C34 15 69 16 69 36 69 49 50 48 50 62" fill="none" stroke="#f4f7fb" stroke-width="8" stroke-linecap="round"/><circle cx="50" cy="76" r="5" fill="#f4f7fb"/>')
for status,active in [('bad',0),('warning',1),('good',2)]:
    lights=''.join('<circle cx="50" cy="%s" r="16" fill="%s" stroke="#090b0c" stroke-width="3"/><circle cx="45" cy="%s" r="5" fill="white" opacity="%s"/>'%(y,(['#ff2617','#ffd300','#42ed17'][i] if i==active else ['#59201a','#51451b','#23451c'][i]),y-5,'.65' if i==active else '.12') for i,y in enumerate([29,75,121]))
    save(status,'<defs>'+metal+'</defs><rect x="18" y="4" width="64" height="142" rx="12" fill="url(#metal)" stroke="#454f58" stroke-width="4"/><path d="M12 12L2 24 18 24M82 12L98 24H82M12 58L2 70H18M82 58L98 70H82M12 104L2 116H18M82 104L98 116H82" fill="#525b65"/>'+lights,w=100,h=150)
colors=['#ff3317','#ffb319','#f8ed25','#8fd735','#2dcb72','#32dbe1','#3299f7','#5446c5','#a837c1','#f442a1','#df223d','#c85f20']
flower='<g transform="translate(81 81)">'+''.join('<path d="M0 0Q-25-27-12-73Q3-82 15-64Q29-27 0 0z" transform="rotate(%s)" fill="%s" stroke="#c4b67c" stroke-width="2.5"/>'%(i*30,color) for i,color in enumerate(colors))+'<circle r="6" fill="#efead4"/></g>'
logo='<defs>'+gradient('chrome',['#fafafa','#77828e','#e7e9eb','#181b20','#b7bec7'])+'</defs>'+flower+'<g font-family="Impact, Arial Black, DejaVu Sans" font-weight="900" fill="url(#chrome)" stroke="#89939b" stroke-width=".65"><text x="173" y="70" font-size="36">LINUX LIVE</text><text x="173" y="112" font-size="33">USB CREATOR</text></g>'
save('logo',logo,450,150);save('lili','<g transform="translate(-5 -5) scale(1.12)">'+flower+'</g>',170,170)
# The original backdrop is the USB trident rotated 154 degrees, not a ribbon.
# Map the rainbow to screen X so its stripes stay aligned across all branches.
rainbow='<linearGradient id="rainbow" gradientUnits="userSpaceOnUse" x1="0" y1="0" x2="450" y2="0" gradientTransform="translate(477 900) scale(1.219512) rotate(-154) translate(-78 -87)"><stop stop-color="#c31d13"/><stop offset=".17" stop-color="#e3900b"/><stop offset=".32" stop-color="#b5c719"/><stop offset=".48" stop-color="#10a15c"/><stop offset=".61" stop-color="#12b6d4"/><stop offset=".74" stop-color="#2442ad"/><stop offset=".86" stop-color="#6b1b98"/><stop offset="1" stop-color="#d30c8b"/></linearGradient>'
branches='M477 825V115M477 735L332 590Q296 554 296 515V440M477 600L655 422Q690 391 690 350V275'
trident='<g transform="translate(78 87) rotate(154) scale(.82) translate(-477 -900)"><path d="'+branches+'" fill="none" stroke="#aeb4bc" stroke-width="80" stroke-linejoin="round"/><path d="'+branches+'" fill="none" stroke="url(#rainbow)" stroke-width="72" stroke-linejoin="round"/><g fill="url(#rainbow)" stroke="#b8bcc3" stroke-width="5"><circle cx="477" cy="900" r="90"/><circle cx="296" cy="440" r="57"/><rect x="642" y="227" width="96" height="96"/><path d="M477 15L402 145H552z"/></g></g>'
panels=''
for y,height in [(148,84),(245,125),(386,96),(496,97),(607,107)]:
    panels+='<rect x="47" y="%s" width="343" height="%s" rx="10" fill="url(#panel)" fill-opacity=".82" stroke="#484b50" stroke-width=".65"/>'%(y,height)
    panels+='<path d="M56 %sH376" stroke="#ed0c24" stroke-width="5" opacity=".28"/><path d="M56 %sH376" stroke="#f15664" stroke-width="1.4"/>'%(y+26,y+26)
bg='<defs>'+rainbow+gradient('panel',['#15171b','#08090b','#111317'])+'</defs>'+trident+panels+logo+'<g transform="translate(57 181) scale(.58 .61)">'+usb+'</g><g transform="translate(56 421) scale(.55)">'+pie+'</g>'
save('GUI',bg,450,750)
for name in ['iso','cd','download','refresh','launch','close','min','back','help']:
    # The same vector path stays sharp; hover uses a subtle lighter overlay.
    data=(OUT/(name+'.svg')).read_text().replace('</svg>','<rect x="1" y="1" width="98" height="98" rx="10" fill="white" opacity=".09"/></svg>')
    (OUT/(name+'_hover.svg')).write_text(data)
print('Scalable artwork generated')
