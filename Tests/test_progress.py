#!/usr/bin/env python3
"""Verify live administrator-log delivery without elevation or device access."""
import json
import os
from pathlib import Path
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

PRIVATE=tempfile.TemporaryDirectory(prefix="lili-progress-")
os.environ["LILI_SUPPORT"]=PRIVATE.name
os.environ.setdefault("QT_QPA_PLATFORM","offscreen")
ROOT=Path(__file__).resolve().parent.parent
sys.path[:0]=[str(ROOT/"Sources"),str(ROOT/"Backend")]
from PySide6.QtCore import QObject,QProcess,QEventLoop,QTimer
from PySide6.QtWidgets import QApplication
from app import Task

APPLICATION=QApplication([])

class ProgressTests(unittest.TestCase):
    def run_worker(self,failure=False):
        owner=QObject();loop=QEventLoop();progress=[];finished=[]
        def arguments(task,args):
            # Replace osascript only in this test; no administrator prompt runs.
            if failure=="device":
                error=json.dumps({"event":"error","message":"[Errno 1] Operation not permitted: '/dev/rdisk9'"})+"\n"
                code="import sys;open(%r,'w').write(%r);print('execution error: command failed',file=sys.stderr);sys.exit(1)"%(str(task.event_log),error)
            elif failure:
                code="import sys;print('Authorization cancelled',file=sys.stderr);sys.exit(1)"
            else:
                event=json.dumps({"event":"progress","fraction":0.25,"message":"Writing image to USB"})+"\n"
                result=json.dumps({"event":"result","value":{"status":"verified"}})+"\n"
                code="import time;f=open(%r,'a',buffering=1);f.write(%r);f.flush();time.sleep(.3);f.write(%r);f.flush();time.sleep(.8);f.write(%r);f.close()"%(str(task.event_log),event[:12],event[12:],result)
            QProcess.setArguments(task,["-u","-c",code])
        def completed(value,error):
            finished.append((value,error,time.monotonic()));loop.quit()
        with patch("app.sys.platform","darwin"),patch.object(Task,"setProgram",lambda task,program:QProcess.setProgram(task,sys.executable)),patch.object(Task,"setArguments",arguments):
            task=Task(owner,["install","unused-test-plan"],completed,lambda fraction,message:progress.append((fraction,message,time.monotonic())),administrator=True)
        QTimer.singleShot(5000,loop.quit);loop.exec()
        self.assertTrue(finished,"Worker did not finish")
        self.assertFalse(task.poll.isActive())
        return progress,finished[0]

    def test_progress_arrives_before_completion_and_partial_lines_are_preserved(self):
        progress,(value,error,ended)=self.run_worker()
        self.assertEqual(value,{"status":"verified"});self.assertIsNone(error)
        self.assertEqual(len(progress),1)
        self.assertEqual(progress[0][:2],(0.25,"Writing image to USB"))
        self.assertLess(progress[0][2],ended-0.2)

    def test_cancelled_authorization_reports_failure_without_worker_events(self):
        progress,(value,error,ended)=self.run_worker(True)
        self.assertFalse(progress);self.assertIsNone(value)
        self.assertIn("Authorization cancelled",error)

    def test_device_permission_error_explains_recovery(self):
        with patch("app.sys.platform","darwin"):
            progress,(value,error,ended)=self.run_worker("device")
        self.assertIsNone(value);self.assertIn("Full Disk Access",error)
        self.assertNotIn("execution error",error)

if __name__=="__main__":unittest.main(verbosity=2)
