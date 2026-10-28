# SPDX-License-Identifier: GPL-3.0-only
"""Scale the whole Qt application, including fonts, dialogs and hit targets."""
import os

def choose_scale(choice,width,height):
    fit=min((width-24)/450,(height-32)/750)
    allowed=[value for value in [0.75,1.0,1.25,1.5,1.75,2.0] if value<=fit]
    maximum=max(allowed or [0.75])
    try:requested=float(choice)
    except (ValueError,TypeError):requested=1.5
    return min(maximum,max(0.75,requested))

def apply_scale(application,config,command):
    current=float(os.environ.get('QT_SCALE_FACTOR','1'))
    screen=application.primaryScreen().availableGeometry()
    target=choose_scale(config.get('General',{}).get('ui_scale','auto'),screen.width()*current,screen.height()*current)
    if abs(current-target)>0.01:
        os.environ['QT_SCALE_FACTOR']=str(target)
        os.execv(command[0],command)
