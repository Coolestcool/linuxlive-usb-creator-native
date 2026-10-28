# SPDX-License-Identifier: GPL-3.0-only
"""Render vectors at the current display density and cache only that exact size."""
from PySide6.QtCore import QRectF
from PySide6.QtGui import QImage,QPainter,QPixmap
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QWidget

def render_vector(renderer,width,height,density):
    image=QImage(round(width*density),round(height*density),QImage.Format_ARGB32_Premultiplied);image.fill(0)
    painter=QPainter(image);painter.setRenderHint(QPainter.Antialiasing);renderer.render(painter,QRectF(image.rect()));painter.end()
    image.setDevicePixelRatio(density);return QPixmap.fromImage(image)

class VectorPicture(QWidget):
    def __init__(self,parent,path,rect):
        super().__init__(parent);self.setGeometry(*rect);self.renderer=QSvgRenderer(self);self.set_asset(path)
    def set_asset(self,path):self.renderer.load(str(path));self.cache=None;self.update()
    def paintEvent(self,event):
        key=(self.width(),self.height(),self.devicePixelRatioF())
        if self.cache is None or self.cache[0]!=key:self.cache=(key,render_vector(self.renderer,*key))
        painter=QPainter(self);painter.drawPixmap(0,0,self.cache[1])
