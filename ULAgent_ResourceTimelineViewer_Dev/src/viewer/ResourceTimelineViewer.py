from __future__ import annotations
import csv, json, re, sys
from pathlib import Path
from datetime import datetime
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPen, QPainterPath, QPixmap, QAction, QKeySequence
from PySide6.QtWidgets import QApplication,QMainWindow,QWidget,QVBoxLayout,QHBoxLayout,QPushButton,QLabel,QFileDialog,QTableWidget,QTableWidgetItem,QSplitter,QTextEdit,QTabWidget,QMessageBox,QComboBox,QAbstractItemView,QGraphicsView,QGraphicsScene,QGraphicsPixmapItem,QToolTip

THEMES = {
    "Light": {"window":"#eef4f9","panel":"#ffffff","panel_alt":"#f8fafc","text":"#243b53","subtext":"#526d82","border":"#cbd6df","grid":"#cbd6df","button":"#ffffff","button_hover":"#e8f0f6","selection":"#dbeafe","tooltip_bg":"#fffbea","tooltip_text":"#17202a","cluster":"#0f766e"},
    "Tactical Olive": {"window":"#151a16","panel":"#1d241e","panel_alt":"#242d25","text":"#d8ded6","subtext":"#97a394","border":"#3a493c","grid":"#405044","button":"#252e26","button_hover":"#334036","selection":"#526b4d","tooltip_bg":"#273129","tooltip_text":"#eff4ec","cluster":"#7f9b72"},
    "Mission Control": {"window":"#0f1720","panel":"#162330","panel_alt":"#1b2b39","text":"#d7e3ea","subtext":"#91a6b3","border":"#304656","grid":"#314b5d","button":"#1a2b38","button_hover":"#243b4a","selection":"#254f5c","tooltip_bg":"#152b35","tooltip_text":"#e7f4f6","cluster":"#63b3a6"}
}
def theme_stylesheet(t):
    return (
        "QMainWindow,QWidget { background:"+t["window"]+"; color:"+t["text"]+"; }"
        "QPushButton,QComboBox { background:"+t["button"]+"; color:"+t["text"]+"; border:1px solid "+t["border"]+"; border-radius:4px; padding:6px 10px; }"
        "QPushButton:hover,QComboBox:hover { background:"+t["button_hover"]+"; }"
        "QPushButton:disabled { color:"+t["subtext"]+"; background:"+t["panel_alt"]+"; }"
        "QTableWidget,QTextEdit { background:"+t["panel"]+"; color:"+t["text"]+"; gridline-color:"+t["border"]+"; selection-background-color:"+t["selection"]+"; }"
        "QHeaderView::section { background:"+t["panel_alt"]+"; color:"+t["text"]+"; border:1px solid "+t["border"]+"; padding:4px; }"
        "QTabWidget::pane { border:1px solid "+t["border"]+"; background:"+t["panel"]+"; }"
        "QTabBar::tab { background:"+t["panel_alt"]+"; color:"+t["subtext"]+"; padding:7px 12px; border:1px solid "+t["border"]+"; }"
        "QTabBar::tab:selected { background:"+t["panel"]+"; color:"+t["text"]+"; }"
        "QSplitter::handle { background:"+t["border"]+"; }"
        "QToolTip { background:"+t["tooltip_bg"]+"; color:"+t["tooltip_text"]+"; border:1px solid "+t["border"]+"; }"
    )

def parse_iso(s):
    if not s:return None
    try:return datetime.fromisoformat(str(s).replace('Z','+00:00'))
    except Exception:return None

def parse_log_ts(line):
    m=re.match(r'^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d+) ([+-]\d{2}:\d{2})',line)
    try:return datetime.strptime(m.group(1)+m.group(2),'%Y-%m-%d %H:%M:%S.%f%z') if m else None
    except Exception:return None

class Store:
    def __init__(self):self.reset()
    def reset(self):self.events=[];self.resources=[];self.files={};self.loaded=[]
    def add_file(self,fid,fn,role,status,kind,source='STATUS'):
        k=fid or fn
        if not k:return
        d=self.files.setdefault(k,{'fileId':fid,'fileName':fn or ('[LOG] '+fid[:16]+'...'),'type':kind or 'UNKNOWN','status':status or 'UNKNOWN','roles':set(),'sources':set()})
        if fid:d['fileId']=fid
        if fn and (not d.get('fileName') or d.get('fileName','').startswith('[LOG] ')):d['fileName']=fn
        if kind and (source=='STATUS' or d.get('type') in ('','UNKNOWN','LOG')):d['type']=kind
        if status and (source=='STATUS' or d.get('status') in ('','UNKNOWN','LOG_ONLY')):d['status']=status
        if role:d['roles'].add(role)
        if source:d['sources'].add(source)
    def role(self,p):
        s=str(p).lower();return 'Sender' if 'sender' in s else ('Receiver' if 'receiver' in s else ('ULsight' if 'ulsight' in s else 'Unknown'))
    def load(self,root):
        self.reset()
        for p in Path(root).rglob('*'):
            if not p.is_file():continue
            n=p.name.lower()
            try:
                if n=='all_results.json':self.status_json(p)
                elif n.endswith('.log') and ('ulagent.sender-' in n or 'ulagent.receiver-' in n):self.log(p)
                elif n.endswith('.csv') and n not in ('records.csv','status.csv','execution_info.csv'):self.resource(p)
            except Exception as e:self.loaded.append((str(p),'ERROR '+str(e)))
    def status_json(self,p):
        o=json.loads(p.read_text(encoding='utf-8-sig'));role=o.get('executionInfo',{}).get('target') or self.role(p);recs=o.get('records',[])
        for r in recs:
            fid=str(r.get('fileId',''));fn=str(r.get('fileName',''));status=str(r.get('status') or r.get('registrationStatus') or r.get('receiveStatus') or '')
            self.add_file(fid,fn,role,status,str(r.get('logType','')),'STATUS')
            self.events.append({'time':parse_iso(r.get('updatedAt')),'raw':r.get('updatedAt'),'role':role,'point':'D' if role=='Sender' else 'H','type':'STATUS','fileId':fid,'fileName':fn,'status':status,'error':r.get('lastErrorCode') or r.get('registrationErrorCode') or r.get('receiveErrorCode'),'source':'STATUS','message':json.dumps(r,ensure_ascii=False)})
        self.loaded.append((str(p),f'{len(recs)} records'))
    def log(self,p):
        role=self.role(p);count=0;pending=[]
        error_code_rx=re.compile(r'ErrorCode:\s*([A-Z0-9_]+)',re.I)
        for line in p.read_text(encoding='utf-8-sig',errors='replace').splitlines():
            ts=parse_log_ts(line)
            if not ts:continue
            low=line.lower();typ='LOG';point='E' if role=='Sender' else 'I';error='';fn=''
            if role=='Sender' and 'discovered ' in low and ' file ' in low:
                typ='DISCOVERED';point='B'
                mfn=re.search(r'\bfile\s+(.+)$',line,re.I);fn=mfn.group(1).strip() if mfn else ''
            elif role=='Sender' and re.search(r'\bsending\s+[0-9a-f]{64}\s+from chunk',line,re.I):
                typ='TRANSFER_START';point='C'
            elif role=='Sender' and 'receiver durably accepted' in low:
                typ='TRANSFER_ACCEPTED';point='C'
            elif role=='Sender' and 'deleted source file for' in low:
                typ='SOURCE_DELETED';point='E'
            elif 'hosting starting' in low or 'application started' in low:
                typ='SYSTEM_START'
            elif 'shutting down' in low or 'hosting stopped' in low or 'receiver is stopping' in low:
                typ='SYSTEM_STOP'
            elif 'failed permanently' in low or '[err]' in low:
                typ='ERROR'
            elif 'will retry at' in low and 'registration' in low:
                typ='REGISTRATION_RETRY';point='I'
            elif 'durably stored' in low:
                typ='RECEIVED';point='G'
            elif 'responded 200' in low and 'filetransferservice/transfer' in low:
                typ='TRANSFER_RESPONSE';point='C'
            m=re.search(r'\b[0-9A-F]{64}\b',line,re.I);fid=m.group(0) if m else ''
            em=error_code_rx.search(line)
            if em:error=em.group(1).upper()
            event={'time':ts,'raw':line[:34],'role':role,'point':point,'type':typ,'fileId':fid,'fileName':fn,'status':'','error':error,'source':'LOG','message':line}
            self.events.append(event);count+=1
            if role=='Sender' and typ=='DISCOVERED':
                pending.append(event)
            if role=='Sender' and typ=='TRANSFER_START' and fid and pending:
                discovered=pending.pop(0);discovered['fileId']=fid;fn=discovered.get('fileName','');event['fileName']=fn
                self.add_file(fid,fn,role,'LOG_ONLY','LOG','LOG')
            elif fid:self.add_file(fid,'',role,'LOG_ONLY','LOG','LOG')
        for orphan in pending:
            if orphan.get('fileName'):self.add_file('',orphan['fileName'],role,'LOG_ONLY','LOG','LOG')
        self.loaded.append((str(p),f'{count} log events'))
    def resource(self,p):
        if p.name.lower().startswith('synthetic_'):
            role=self.role(p);count=0;missing=0
            with p.open(encoding='utf-8-sig',newline='') as f:
                for row in csv.DictReader(f):
                    ts=parse_iso(row.get('Timestamp'))
                    if not ts:continue
                    role=row.get('Role') or role
                    for metric,value in row.items():
                        if metric in ('Timestamp','Role','Synthetic'):continue
                        if value is None or value=='':val=None;missing+=1
                        else:
                            try:val=float(value)
                            except ValueError:continue
                        self.resources.append({'time':ts,'raw':row.get('Timestamp'),'role':role,'point':'F' if role=='Sender' else 'J','metric':metric,'value':val,'synthetic':True,'source':'SYNTHETIC_RESOURCE'})
                    count+=1
            self.loaded.append((str(p),f'{count} synthetic resource rows; missing={missing}'));return

        with p.open(encoding='utf-8-sig',newline='') as f:
            reader=csv.reader(f);headers=next(reader,None)
            if not headers:
                self.loaded.append((str(p),'resource candidate (empty)'));return
            normalized=[h.strip().lower() for h in headers]
            header_text=' '.join(normalized)
            role='Sender' if 'ulagent.sender' in header_text else ('Receiver' if 'ulagent.receiver' in header_text else 'Unknown')
            if role=='Unknown':
                self.loaded.append((str(p),'resource candidate (PDH role unknown)'));return
            proc='process(ulagent.'+role.lower()+')'
            def find_index(*parts):
                for i,h in enumerate(normalized):
                    if all(part in h for part in parts):return i
                return None
            indexes={
                'CPU_Percent':find_index('processor(_total)','% processor time'),
                'ULAgent_WorkingSetPrivate_MB':find_index(proc,'working set - private'),
                'ULAgent_CPU_Percent':find_index(proc,'% processor time'),
                'ULAgent_IO_Write_BytesSec':find_index(proc,'io write bytes/sec'),
                'ULAgent_IO_Read_BytesSec':find_index(proc,'io read bytes/sec'),
                'Disk_Write_BytesSec':find_index('physicaldisk(_total)','disk write bytes/sec'),
                'Disk_Read_BytesSec':find_index('physicaldisk(_total)','disk read bytes/sec'),
                'Memory_Available_MB':find_index('memory','available bytes')}
            send_indexes=[i for i,h in enumerate(normalized) if 'network interface(' in h and 'bytes sent/sec' in h]
            recv_indexes=[i for i,h in enumerate(normalized) if 'network interface(' in h and 'bytes received/sec' in h]
            count=0;missing=0
            def number(row,i):
                nonlocal missing
                if i is None or i>=len(row) or row[i].strip()=='':missing+=1;return None
                try:return float(row[i].strip())
                except ValueError:missing+=1;return None
            def network_total(row,indices):
                values=[]
                for i in indices:
                    v=number(row,i)
                    if v is not None:values.append(v)
                return sum(values) if values else None
            for row in reader:
                if not row:continue
                ts=parse_iso(row[0].strip())
                if not ts:continue
                values={metric:number(row,i) for metric,i in indexes.items()}
                if values['ULAgent_WorkingSetPrivate_MB'] is not None:values['ULAgent_WorkingSetPrivate_MB']/=1048576.0
                if values['Memory_Available_MB'] is not None:values['Memory_Available_MB']/=1048576.0
                values['Network_Send_BytesSec']=network_total(row,send_indexes)
                values['Network_Receive_BytesSec']=network_total(row,recv_indexes)
                for metric,val in values.items():
                    self.resources.append({'time':ts,'raw':row[0].strip(),'role':role,'point':'F' if role=='Sender' else 'J','metric':metric,'value':val,'synthetic':False,'source':'PDH_RESOURCE'})
                count+=1
            self.loaded.append((str(p),f'{count} PDH resource rows; role={role}; missing={missing}'))

def event_short_label(event):
    labels={
        'DISCOVERED':'B Discover','TRANSFER_START':'C Send','TRANSFER_ACCEPTED':'C Accepted',
        'TRANSFER_RESPONSE':'C Response','SOURCE_DELETED':'E Delete','RECEIVED':'G Stored',
        'REGISTRATION_RETRY':'I Retry','ERROR':'I Error','SYSTEM_START':'Start','SYSTEM_STOP':'Stop'}
    if event.get('type')=='STATUS':return str(event.get('point',''))+' Status'
    return labels.get(event.get('type'),str(event.get('point','')))

class DiagramView(QGraphicsView):
    def __init__(self):
        super().__init__();self.theme=THEMES['Light'];self.setScene(QGraphicsScene(self));self.pixmap_item=None;self.setDragMode(QGraphicsView.NoDrag);self.setAlignment(Qt.AlignCenter);self.apply_theme(self.theme);self.setRenderHint(QPainter.SmoothPixmapTransform,True)
    def apply_theme(self,theme):
        self.theme=theme;self.setStyleSheet("QGraphicsView { background:"+theme["panel"]+"; border:1px solid "+theme["border"]+"; }")
    def set_image(self,path):
        pix=QPixmap(str(path))
        if pix.isNull():return False
        self.scene().clear();self.pixmap_item=QGraphicsPixmapItem(pix);self.pixmap_item.setTransformationMode(Qt.SmoothTransformation);self.scene().addItem(self.pixmap_item);self.scene().setSceneRect(self.pixmap_item.boundingRect());self.fit_image();self.setToolTip(str(path));return True
    def fit_image(self):
        if self.pixmap_item:
            self.resetTransform();self.fitInView(self.pixmap_item,Qt.KeepAspectRatio)
    def resizeEvent(self,event):
        super().resizeEvent(event);self.fit_image()


class Timeline(QWidget):
    clusterActivated=Signal(object)
    def __init__(self):
        super().__init__();self.theme=THEMES['Light'];self.events=[];self.time_window=None;self.cluster_regions=[];self.detail_mode=False;self.setMinimumHeight(205);self.setCursor(Qt.PointingHandCursor)
    def apply_theme(self,theme):
        self.theme=theme;self.update()
    def set_events(self,e,window=None,detail=False):
        self.events=[x for x in e if x.get('time')];self.time_window=window;self.detail_mode=detail;self.cluster_regions=[];self.update()
    def _clusters(self,events,lo,hi,left,right):
        clusters=[];pixel_threshold=72.0;span=max(hi-lo,0.001)
        for e in events:
            if not clusters:clusters.append([e]);continue
            prev=clusters[-1][-1];gap_px=(e['time'].timestamp()-prev['time'].timestamp())*(right-left)/span
            if gap_px>pixel_threshold:clusters.append([e])
            else:clusters[-1].append(e)
        return clusters
    def mousePressEvent(self,event):
        pos=event.position()
        for x,y,w,h,cluster in self.cluster_regions:
            if x<=pos.x()<=x+w and y<=pos.y()<=y+h and len(cluster)>1:
                self.clusterActivated.emit(cluster);return
        super().mousePressEvent(event)
    def paintEvent(self,_):
        q=QPainter(self);q.fillRect(self.rect(),QColor(self.theme['panel']));q.setRenderHint(QPainter.Antialiasing)
        left=108;right=self.width()-25;flow_y=92
        q.setPen(QColor(self.theme['text']));q.drawText(18,24,'処理フロー共通時間軸  Raw Timestamp / 自動時計補正なし')
        q.drawText(max(455,self.width()-700),24,'□ Status  ● Log  橙 Retry  赤 Error  ◎ 近接イベント(クリックで拡大)')
        q.setPen(QPen(QColor(self.theme['grid']),2));q.drawLine(left,flow_y,right,flow_y);q.setPen(QColor(self.theme['subtext']));q.drawText(18,flow_y+4,'A→L Flow')
        if not self.events:q.drawText(left,55,'Evidenceを読み込むとA～Lの観測イベントを表示します。');return
        events=sorted(self.events,key=lambda e:e['time']);lo=self.time_window[0].timestamp() if self.time_window else events[0]['time'].timestamp();hi=self.time_window[1].timestamp() if self.time_window else max(lo+1,events[-1]['time'].timestamp());hi=max(lo+0.001,hi)
        colors={'ERROR':'#dc3545','SYSTEM_STOP':'#555555','SYSTEM_START':'#16a34a','STATUS':'#2563eb','RECEIVED':'#7c3aed','TRANSFER_RESPONSE':'#0b79d0','REGISTRATION_RETRY':'#f59e0b','LOG':'#8a9baa','DISCOVERED':'#2563eb','TRANSFER_START':'#2563eb','TRANSFER_ACCEPTED':'#2563eb','SOURCE_DELETED':'#2563eb'}
        clusters=self._clusters(events,lo,hi,left,right);self.cluster_regions=[];slots={}
        for cluster in clusters:
            mid=sum(e['time'].timestamp() for e in cluster)/len(cluster);x=left+(right-left)*(mid-lo)/(hi-lo)
            if len(cluster)>1:
                labels='/'.join(str(e.get('point','')) for e in cluster);c=QColor(self.theme['cluster']);q.setPen(QPen(c,2));q.setBrush(c);q.drawEllipse(int(x)-7,flow_y-7,14,14)
                text=labels+' ('+str(len(cluster))+')';q.setPen(c);q.drawText(int(x)-18,flow_y-22,text);self.cluster_regions.append((x-22,flow_y-38,90,50,cluster));continue
            e=cluster[0];typ=e.get('type','LOG');c=QColor(colors.get(typ,'#8a9baa'));q.setPen(QPen(c,2));q.setBrush(c);ex=left+(right-left)*(e['time'].timestamp()-lo)/(hi-lo)
            if typ in ('SYSTEM_START','SYSTEM_STOP'):q.drawLine(int(ex),flow_y-14,int(ex),flow_y+14)
            elif typ=='STATUS':q.drawRect(int(ex)-5,flow_y-5,10,10)
            else:q.drawEllipse(int(ex)-5,flow_y-5,10,10)
            bucket=round(ex/48);slot=slots.get(bucket,0);slots[bucket]=slot+1;label_y=flow_y-22-(slot%6)*15;label=event_short_label(e);q.setPen(QPen(c,1));q.drawLine(int(ex),flow_y-7,int(ex),label_y+4);q.drawText(int(ex)-5,label_y,label)
        q.setPen(QColor('#2563eb'));q.drawText(left,132,'F: Sender Resource');q.setPen(QColor('#7c3aed'));q.drawText(left+145,132,'J: Receiver Resource');q.setPen(QColor(self.theme['subtext']));q.drawText(left+310,132,'K/L: Not Observed')
        start_txt=datetime.fromtimestamp(lo,events_tz(events)).isoformat(timespec='milliseconds');end_txt=datetime.fromtimestamp(hi,events_tz(events)).isoformat(timespec='milliseconds');q.setPen(QColor(self.theme['subtext']));q.drawText(left,184,start_txt);q.drawText(self.width()-405,166,380,28,Qt.AlignRight|Qt.AlignVCenter,end_txt)

def events_tz(items):
    for x in items:
        t=x.get('time')
        if t is not None and t.tzinfo is not None:return t.tzinfo
    return None

class ResourceChart(QWidget):
    def __init__(self):
        super().__init__();self.theme=THEMES['Light'];self.samples=[];self.time_window=None;self.resource_metric='CPU_Percent';self.hover_x=None;self.plot_bounds=None;self.hover_data=[];self.hover_copy_text='';self.range_dragging=False;self.range_start_x=None;self.range_end_x=None;self.range_start_time=None;self.range_end_time=None;self.setMouseTracking(True);self.setMinimumHeight(245)
    def apply_theme(self,theme):
        self.theme=theme;self.update()
    def set_data(self,samples,window=None,metric=None):self.samples=samples;self.time_window=window;self.resource_metric=metric or self.resource_metric;self.update()
    def paintEvent(self,_):
        q=QPainter(self);q.fillRect(self.rect(),QColor(self.theme['panel']));q.setRenderHint(QPainter.Antialiasing)
        mode='SYNTHETIC' if self.samples and all(x.get('synthetic') for x in self.samples) else 'REAL/PDH';q.setPen(QColor(self.theme['text']));q.drawText(12,20,'OS Resource overlay: F(Sender) / J(Receiver)  ['+mode+']  '+self.resource_metric+'  空欄=Missing / 0=実値0')
        all_data=[x for x in self.samples if x.get('metric')==self.resource_metric and x.get('time')]
        data=list(all_data);resource_context=False
        if self.time_window:
            view_lo,view_hi=self.time_window;inside=[x for x in all_data if view_lo<=x['time']<=view_hi];context=[]
            for role in ('Sender','Receiver'):
                role_data=sorted([x for x in all_data if x.get('role')==role],key=lambda x:x['time'])
                before=[x for x in role_data if x['time']<view_lo];after=[x for x in role_data if x['time']>view_hi]
                if before:context.append(before[-1])
                if after:context.append(after[0])
            data=inside+context;resource_context=bool(context)
        if not data:q.drawText(12,48,'表示対象のResourceデータなし');return
        if self.time_window and resource_context:
            lo=min([self.time_window[0].timestamp()]+[x['time'].timestamp() for x in data]);hi=max([self.time_window[1].timestamp()]+[x['time'].timestamp() for x in data])
        else:
            lo=(self.time_window[0].timestamp() if self.time_window else min(x['time'].timestamp() for x in data));hi=(self.time_window[1].timestamp() if self.time_window else max(lo+1,max(x['time'].timestamp() for x in data)))
        hi=max(lo+0.001,hi);top=38;bottom=self.height()-36;left=108;right=self.width()-25
        if self.time_window and resource_context:q.setPen(QColor(self.theme['subtext']));q.drawText(300,63,'※ズーム範囲前後の直近実測サンプルを含む')
        self.plot_bounds=(left,right,lo,hi);self.hover_data=list(data)
        colors={'Sender':QColor('#2563eb'),'Receiver':QColor('#7c3aed')}
        q.setPen(QPen(colors['Sender'],3));q.drawLine(12,58,42,58);q.setPen(QColor(self.theme['text']));q.drawText(48,63,'F Sender')
        q.setPen(QPen(colors['Receiver'],3));q.drawLine(120,58,150,58);q.setPen(QColor(self.theme['text']));q.drawText(156,63,'J Receiver')
        for role in ('Sender','Receiver'):
            vals=sorted([x for x in data if x['role']==role],key=lambda x:x['time'])
            pen=QPen(colors[role],2);q.setPen(pen);path=None
            for x in vals:
                if x['value'] is None:path=None;continue
                px=left+(right-left)*(x['time'].timestamp()-lo)/(hi-lo);maxv=max([v['value'] for v in data if v['value'] is not None]+[1]);scale=100.0 if 'Percent' in self.resource_metric else maxv;py=bottom-(bottom-top)*max(0,min(scale,x['value']))/scale
                if path is None:path=QPainterPath();path.moveTo(px,py)
                else:path.lineTo(px,py)
                # zero is a real sample; show a small marker at baseline
                if x['value']==0:q.drawEllipse(int(px)-2,int(py)-2,4,4)
            if path is not None:q.drawPath(path)
        if self.range_dragging and self.range_start_x is not None and self.range_end_x is not None:
            x1=max(left,min(right,self.range_start_x));x2=max(left,min(right,self.range_end_x));q.fillRect(int(min(x1,x2)),top,int(abs(x2-x1)),bottom-top,QColor(99,179,166,55));q.setPen(QPen(QColor(self.theme['cluster']),1,Qt.DashLine));q.drawRect(int(min(x1,x2)),top,int(abs(x2-x1)),bottom-top)
        if self.hover_x is not None and left<=self.hover_x<=right:
            q.setPen(QPen(QColor(self.theme['subtext']),1,Qt.DashLine));q.drawLine(int(self.hover_x),top,int(self.hover_x),bottom)
        q.setPen(QColor(self.theme['subtext']));q.drawLine(left,bottom,right,bottom);start_txt=datetime.fromtimestamp(lo,events_tz(data)).isoformat(timespec='milliseconds');end_txt=datetime.fromtimestamp(hi,events_tz(data)).isoformat(timespec='milliseconds');q.drawText(left,bottom+18,start_txt);q.drawText(self.width()-405,bottom+2,380,28,Qt.AlignRight|Qt.AlignVCenter,end_txt)

    def mouseMoveEvent(self,event):
        if not self.plot_bounds or not self.hover_data:return
        left,right,lo,hi=self.plot_bounds;x=event.position().x()
        if self.range_dragging:
            self.range_end_x=max(left,min(right,x));t1=lo+(self.range_start_x-left)*(hi-lo)/(right-left);t2=lo+(self.range_end_x-left)*(hi-lo)/(right-left);from datetime import datetime,timezone
            self.range_start_time=datetime.fromtimestamp(t1,timezone.utc);self.range_end_time=datetime.fromtimestamp(t2,timezone.utc);QToolTip.showText(event.globalPosition().toPoint(),'開始: '+self.range_start_time.isoformat(timespec='milliseconds')+'\n終了: '+self.range_end_time.isoformat(timespec='milliseconds'),self);self.update();return
        if x<left or x>right:self.hover_x=None;self.update();QToolTip.hideText();return
        target=lo+(x-left)*(hi-lo)/(right-left);lines=[];nearest_times=[]
        for role in ('Sender','Receiver'):
            vals=[v for v in self.hover_data if v.get('role')==role and v.get('value') is not None]
            if not vals:continue
            near=min(vals,key=lambda v:abs(v['time'].timestamp()-target));nearest_times.append(near['time']);unit='%' if 'Percent' in self.resource_metric else ('MB' if self.resource_metric.endswith('_MB') else 'Bytes/sec')
            lines.append(('F Sender' if role=='Sender' else 'J Receiver')+': '+format(near['value'],'.3f')+' '+unit+'  ['+near['time'].isoformat(timespec='milliseconds')+']')
        if lines:
            display_time=min(nearest_times,key=lambda t:abs(t.timestamp()-target));QToolTip.showText(event.globalPosition().toPoint(),display_time.isoformat(timespec='milliseconds')+'\n'+'\n'.join(lines)+'\n\nクリックでコピー',self)
            values={}
            for role in ('Sender','Receiver'):
                vals=[v for v in self.hover_data if v.get('role')==role and v.get('value') is not None]
                values[role]=min(vals,key=lambda v:abs(v['time'].timestamp()-target)) if vals else None
            sender='' if values['Sender'] is None else str(values['Sender']['value']);receiver='' if values['Receiver'] is None else str(values['Receiver']['value'])
            self.hover_copy_text='Timestamp\tMetric\tF Sender\tJ Receiver\n'+display_time.isoformat(timespec='milliseconds')+'\t'+self.resource_metric+'\t'+sender+'\t'+receiver
            self.hover_x=x;self.update()
    def mousePressEvent(self,event):
        if event.button()==Qt.LeftButton and self.plot_bounds:
            left,right,_,_=self.plot_bounds;x=event.position().x()
            if left<=x<=right:
                self.range_dragging=True;self.range_start_x=x;self.range_end_x=x;_,_,lo,hi=self.plot_bounds;from datetime import datetime,timezone;ts=lo+(x-left)*(hi-lo)/(right-left);self.range_start_time=datetime.fromtimestamp(ts,timezone.utc);self.range_end_time=self.range_start_time;event.accept();return
        super().mousePressEvent(event)
    def mouseReleaseEvent(self,event):
        if event.button()==Qt.LeftButton and self.range_dragging and self.plot_bounds:
            left,right,lo,hi=self.plot_bounds;x1=max(left,min(right,self.range_start_x));x2=max(left,min(right,event.position().x()));self.range_dragging=False
            if abs(x2-x1)<5:
                self.range_start_x=self.range_end_x=None;self.update()
                if self.hover_copy_text:QApplication.clipboard().setText(self.hover_copy_text);QToolTip.showText(event.globalPosition().toPoint(),'✓ Resource値をコピーしました',self)
                event.accept();return
            t1=lo+(min(x1,x2)-left)*(hi-lo)/(right-left);t2=lo+(max(x1,x2)-left)*(hi-lo)/(right-left)
            selected=sorted([v for v in self.hover_data if v.get('value') is not None and t1<=v['time'].timestamp()<=t2],key=lambda v:(v['time'],v.get('role','')))
            lines=['Role\tTimestamp\tMetric\tValue']
            for v in selected:lines.append(('F Sender' if v.get('role')=='Sender' else 'J Receiver')+'\t'+v['time'].isoformat(timespec='milliseconds')+'\t'+self.resource_metric+'\t'+str(v['value']))
            self.range_start_x=self.range_end_x=None;self.update()
            if selected:QApplication.clipboard().setText('\n'.join(lines));QToolTip.showText(event.globalPosition().toPoint(),'✓ 選択範囲のResource値 '+str(len(selected))+' 件をコピーしました',self)
            else:QToolTip.showText(event.globalPosition().toPoint(),'選択範囲に実測Resource値がありません',self)
            event.accept();return
        super().mouseReleaseEvent(event)
    def leaveEvent(self,event):
        self.hover_x=None;self.hover_copy_text='';self.update();QToolTip.hideText();super().leaveEvent(event)

class Main(QMainWindow):
    def __init__(self):
        super().__init__();self.store=Store();self.selected_events=[];self.selected_file_name='';self.view_history=[];self.view_index=-1;self.restoring_history=False;self.theme_name='Light';self.setWindowTitle('ULAgent Resource Timeline Viewer v0.15.2');self.resize(1500,900);w=QWidget();self.setCentralWidget(w);v=QVBoxLayout(w);top=QHBoxLayout();b=QPushButton('Evidenceフォルダを開く');b.clicked.connect(self.open_evidence);self.path=QLabel('Evidence: 未選択');self.back_btn=QPushButton('← 戻る');self.back_btn.clicked.connect(self.go_back);self.forward_btn=QPushButton('→ 進む');self.forward_btn.clicked.connect(self.go_forward);overview=QPushButton('全体表示');overview.clicked.connect(self.show_overview);top.addWidget(b);top.addWidget(self.path,1);top.addWidget(self.back_btn);top.addWidget(self.forward_btn);top.addWidget(overview);top.addWidget(QLabel('Theme:'));self.theme_combo=QComboBox();self.theme_combo.addItems(['Light','Tactical Olive','Mission Control']);self.theme_combo.currentTextChanged.connect(self.change_theme);top.addWidget(self.theme_combo);ai=QPushButton('AI解析プロンプト生成');ai.clicked.connect(self.ai_prompt);top.addWidget(ai);v.addLayout(top)
        sp=QSplitter();v.addWidget(sp,1);left=QWidget();lv=QVBoxLayout(left);lv.addWidget(QLabel('対象ファイル'));self.files=QTableWidget(0,5);self.files.setEditTriggers(QAbstractItemView.NoEditTriggers);self.files.setSelectionMode(QAbstractItemView.ExtendedSelection);self.files.setHorizontalHeaderLabels(['FileName','Type','Status','Roles','Source']);self.files.setColumnWidth(0,195);self.files.setColumnWidth(1,85);self.files.setColumnWidth(2,85);self.files.setColumnWidth(3,120);self.files.setColumnWidth(4,80);self.files.cellClicked.connect(self.select_file);left_split=QSplitter(Qt.Vertical);left_split.addWidget(self.files);diagram_box=QWidget();diagram_layout=QVBoxLayout(diagram_box);diagram_layout.setContentsMargins(0,4,0,0);diagram_layout.addWidget(QLabel('A～L システム構成図  （表示領域に自動フィット）'));self.diagram=DiagramView();self.diagram.setMinimumHeight(180);diagram_layout.addWidget(self.diagram,1);left_split.addWidget(diagram_box);left_split.setSizes([520,260]);lv.addWidget(left_split);sp.addWidget(left)
        right=QWidget();rv=QVBoxLayout(right);flow=QLabel('Flow: A(=C substitute) → B → C → D → E → F → G → H → I → J → K → L    ※代用/未観測はEvidenceと区別');rv.addWidget(flow);self.summary=QLabel('Result: UNKNOWN | A: Not Observed | Time correction: OFF');rv.addWidget(self.summary);self.timeline=Timeline();self.timeline.clusterActivated.connect(self.zoom_cluster);rv.addWidget(self.timeline);metric_row=QHBoxLayout();metric_row.addWidget(QLabel('Resource Metric:'));self.metric_combo=QComboBox();self.metric_combo.addItems(['CPU_Percent','Memory_Available_MB','Memory_Used_MB','Disk_Read_BytesSec','Disk_Write_BytesSec','Network_Send_BytesSec','Network_Receive_BytesSec','ULAgent_CPU_Percent','ULAgent_WorkingSetPrivate_MB','ULAgent_IO_Read_BytesSec','ULAgent_IO_Write_BytesSec']);self.metric_combo.currentTextChanged.connect(self.change_metric);metric_row.addWidget(self.metric_combo);metric_row.addStretch(1);rv.addLayout(metric_row);self.resource_chart=ResourceChart();rv.addWidget(self.resource_chart);self.tabs=QTabWidget();self.detail=QTextEdit();self.detail.setReadOnly(True);self.logs=QTableWidget(0,8);self.logs.setEditTriggers(QAbstractItemView.NoEditTriggers);self.logs.setSelectionMode(QAbstractItemView.ExtendedSelection);self.logs.setHorizontalHeaderLabels(['Time','Role','Point','Type','Source','Status','Error','Message']);self.logs.setColumnWidth(0,220);self.logs.setColumnWidth(1,75);self.logs.setColumnWidth(2,50);self.logs.setColumnWidth(3,150);self.logs.setColumnWidth(4,70);self.logs.setColumnWidth(5,100);self.logs.setColumnWidth(6,130);self.evidence=QTableWidget(0,2);self.evidence.setEditTriggers(QAbstractItemView.NoEditTriggers);self.evidence.setSelectionMode(QAbstractItemView.ExtendedSelection);self.evidence.setHorizontalHeaderLabels(['Evidence File','Read Result']);self.evidence.setColumnWidth(0,620);self.evidence.setColumnWidth(1,260);self.tabs.addTab(self.detail,'詳細');self.tabs.addTab(self.logs,'ログ / イベント');self.tabs.addTab(self.evidence,'Evidence読込');rv.addWidget(self.tabs,1);sp.addWidget(right);sp.setSizes([420,1080]);self.load_system_diagram();self.back_action=QAction(self);self.back_action.setShortcut(QKeySequence('Alt+Left'));self.back_action.triggered.connect(self.go_back);self.addAction(self.back_action);self.forward_action=QAction(self);self.forward_action.setShortcut(QKeySequence('Alt+Right'));self.forward_action.triggered.connect(self.go_forward);self.addAction(self.forward_action);self.update_history_buttons();self.change_theme(self.theme_name)
    def change_theme(self,name):
        if name not in THEMES:return
        self.theme_name=name;theme=THEMES[name];QApplication.instance().setStyleSheet(theme_stylesheet(theme));self.timeline.apply_theme(theme);self.resource_chart.apply_theme(theme);self.diagram.apply_theme(theme)
    def push_view_state(self,window,events,summary=None):
        if self.restoring_history:return
        state={'window':window,'events':list(events),'summary':summary or self.summary.text()}
        if self.view_index>=0:
            current=self.view_history[self.view_index]
            if current.get('window')==window and current.get('events')==state['events']:return
        del self.view_history[self.view_index+1:];self.view_history.append(state);self.view_index=len(self.view_history)-1;self.update_history_buttons()
    def restore_view_state(self,state):
        self.restoring_history=True
        try:
            win=state.get('window');events=state.get('events',[]);self.timeline.set_events(events,win,False);self.resource_chart.set_data(self.store.resources,win,self.metric_combo.currentText());self.show_events(events);self.summary.setText(state.get('summary',self.summary.text()))
        finally:self.restoring_history=False
        self.update_history_buttons()
    def go_back(self):
        if self.view_index>0:self.view_index-=1;self.restore_view_state(self.view_history[self.view_index])
    def go_forward(self):
        if 0<=self.view_index<len(self.view_history)-1:self.view_index+=1;self.restore_view_state(self.view_history[self.view_index])
    def update_history_buttons(self):
        can_back=self.view_index>0;can_forward=0<=self.view_index<len(self.view_history)-1
        if hasattr(self,'back_btn'):self.back_btn.setEnabled(can_back);self.forward_btn.setEnabled(can_forward)
        if hasattr(self,'back_action'):self.back_action.setEnabled(can_back);self.forward_action.setEnabled(can_forward)
    def reset_history(self,window,events,summary=None):
        self.view_history=[];self.view_index=-1;self.push_view_state(window,events,summary)
    def event_window_with_padding(self,events,min_seconds=3.0):
        times=[e['time'] for e in events if e.get('time')]
        if not times:return None
        lo=min(times);hi=max(times);span=max((hi-lo).total_seconds(),0.0);pad=max(min_seconds,(span*0.08))
        from datetime import timedelta
        return (lo-timedelta(seconds=pad),hi+timedelta(seconds=pad))
    def zoom_cluster(self,cluster):
        times=sorted(e['time'] for e in cluster if e.get('time'))
        if not times:return
        from datetime import timedelta
        span=max((times[-1]-times[0]).total_seconds(),0.001);pad=max(span*1.5,0.015);win=(times[0]-timedelta(seconds=pad),times[-1]+timedelta(seconds=pad))
        visible=[e for e in (self.selected_events or cluster) if e.get('time') and win[0]<=e['time']<=win[1]]
        self.timeline.set_events(visible,win,False);self.resource_chart.set_data(self.store.resources,win,self.metric_combo.currentText());self.show_events(visible);new_summary=(self.summary.text().split(' | Zoom:')[0])+' | Zoom: '+('/'.join(event_short_label(e) for e in cluster));self.summary.setText(new_summary);self.push_view_state(win,visible,new_summary)
    def file_events(self,fid,fn):
        ev=[e for e in self.store.events if (fid and e.get('fileId')==fid) or e.get('fileName')==fn]
        if not ev and fn:ev=[e for e in self.store.events if e.get('fileName')==fn]
        return ev
    def resizeEvent(self,event):
        super().resizeEvent(event)
        pass
    def load_system_diagram(self):
        candidates=[Path(__file__).resolve().parents[2]/'assets'/'system_flow.png',Path(__file__).resolve().parent/'system_flow.png']
        for path in candidates:
            if path.exists():
                if self.diagram.set_image(path):return
        self.diagram.setToolTip('assets/system_flow.png が見つかりません')
    def current_window(self,events=None):
        ev=[e for e in (events if events is not None else self.store.events) if e.get('time')]
        if not ev:return None
        return (min(e['time'] for e in ev),max(e['time'] for e in ev))
    def change_metric(self,name):
        self.resource_chart.set_data(self.store.resources,self.resource_chart.time_window,name)
    def open_evidence(self):
        p=QFileDialog.getExistingDirectory(self,'Evidenceフォルダを選択')
        if p:self.store.load(p);self.path.setText('Evidence: '+p);self.populate()
    def show_overview(self):
        self.files.clearSelection();self.selected_events=[];self.selected_file_name='';win=self.current_window();self.timeline.set_events(self.store.events,win,False);self.resource_chart.set_data(self.store.resources,win,self.metric_combo.currentText());self.show_events(self.store.events);self.detail.clear()
        self.summary.setText(f'Result: UNKNOWN | Files: {len(self.store.files)} | Events: {len(self.store.events)} | Evidence read: {len(self.store.loaded)} | Resource samples: {len(self.store.resources)} | A: Not Observed | Time correction: OFF');self.reset_history(win,self.store.events,self.summary.text())
    def populate(self):
        ds=sorted(self.store.files.values(),key=lambda d:(d.get('fileName','').startswith('[LOG] '),d.get('fileName','')));self.files.setRowCount(len(ds))
        for i,d in enumerate(ds):
            vals=[d['fileName'],d['type'],d['status'],'/'.join(sorted(d['roles'])),'/'.join(sorted(d.get('sources',[])))]
            for j,x in enumerate(vals):self.files.setItem(i,j,QTableWidgetItem(str(x)))
            self.files.item(i,0).setData(256,d.get('fileId',''))
        self.evidence.setRowCount(len(self.store.loaded))
        for i,(path,result) in enumerate(self.store.loaded):
            self.evidence.setItem(i,0,QTableWidgetItem(path));self.evidence.setItem(i,1,QTableWidgetItem(result))
        win=self.current_window();self.timeline.set_events(self.store.events,win,False);self.resource_chart.set_data(self.store.resources,win,self.metric_combo.currentText());self.show_events(self.store.events);self.summary.setText(f'Result: UNKNOWN | Files: {len(ds)} | Events: {len(self.store.events)} | Evidence read: {len(self.store.loaded)} | Resource samples: {len(self.store.resources)} | A: Not Observed | Time correction: OFF');self.reset_history(win,self.store.events,self.summary.text())
    def show_events(self,ev):
        a=sorted([e for e in ev if e.get('time')],key=lambda e:e['time']);self.logs.setRowCount(len(a))
        for i,e in enumerate(a):
            for j,x in enumerate([e['time'].isoformat(),e['role'],e['point'],e['type'],e.get('source',''),e.get('status') or '',e.get('error') or '',e['message']]):self.logs.setItem(i,j,QTableWidgetItem(str(x)))
    def select_file(self,row,_):
        fn=self.files.item(row,0).text();fid=self.files.item(row,0).data(256) or ''
        d=next((x for x in self.store.files.values() if x['fileId']==fid),next(x for x in self.store.files.values() if x['fileName']==fn))
        ev=self.file_events(fid,fn);base_times=[e['time'] for e in ev if e.get('time')]
        if base_times:
            lo=min(base_times);hi=max(base_times);system_types={'SYSTEM_START','SYSTEM_STOP'};ev += [e for e in self.store.events if e.get('type') in system_types and e.get('time') and lo<=e['time']<=hi and e not in ev]
        self.selected_events=ev;self.selected_file_name=fn
        win=self.event_window_with_padding(ev,3.0);self.timeline.set_events(ev,win,False);self.resource_chart.set_data(self.store.resources,win,self.metric_combo.currentText());self.show_events(ev)
        errs=[e for e in ev if e.get('error') or e['type']=='ERROR'];attn=[e for e in ev if e.get('type')=='REGISTRATION_RETRY'];result='ERROR' if errs else ('ATTENTION' if attn else ('OBSERVED' if ev else 'UNKNOWN'));ts=sorted([e['time'] for e in ev if e.get('time')]);span=ts[-1].timestamp()-ts[0].timestamp() if len(ts)>1 else None
        info={**d,'roles':sorted(d['roles']),'sources':sorted(d.get('sources',[])),'viewerResult':result,'eventCount':len(ev),'observedSpanSeconds':span if span is not None else 'Not Observed','note':'Observed timestamp span only; not automatically treated as processing duration.'};self.detail.setPlainText(json.dumps(info,ensure_ascii=False,indent=2));self.summary.setText(f'Selected: {fn} | Result: {result} | Events: {len(ev)} | A: Not Observed | Time correction: OFF');self.reset_history(win,ev,self.summary.text())
    def ai_prompt(self):
        rows=[]
        for r in range(self.logs.rowCount()):
            rows.append(' | '.join(self.logs.item(r,c).text() if self.logs.item(r,c) else '' for c in range(self.logs.columnCount())))
        selected=self.summary.text()
        text=(
            'あなたはシステム障害解析を支援するエンジニアです。以下の観測事実だけを根拠に解析してください。\n\n'
            '【システム概要】\nLogManager → ULAgent Sender → TLS gRPC → ULAgent Receiver → ULsight。\n'
            'A=ファイル生成・格納、B=Sender処理、C=転送、D=Sender状態、E=Senderログ、F=Senderリソース、'
            'G=Receiver保存、H=Receiver状態、I=Receiverログ、J=Receiverリソース、K=ULsight処理、L=ULsightリソース。\n\n'
            '【Viewer表示状態】\n'+selected+'\n\n'
            '【重要な制約】\n'
            'Aが未取得なら他イベントで代用しない。Raw Timestampを尊重し、PC間の時計差を勝手に補正しない。'
            '0と欠損を区別する。Status情報からSQLite内部SQL実行履歴を推定しない。観測されていない情報を事実として補完しない。'
            'AIの推定はEvidenceと区別する。\n\n'
            '【観測Evidence】\n'+('\n'.join(rows) if rows else '表示中のイベントなし')+'\n\n'
            '【回答形式】\n1. 観測された事実\n2. Attention / Error / Unknown\n3. 原因候補と根拠\n'
            '4. 判断できないこと\n5. 次に確認すべきEvidence'
        )
        QApplication.clipboard().setText(text)
        QMessageBox.information(self,'AI解析プロンプト','クリップボードへコピーしました。ViewerからAIサービスへの通信は行いません。')

if __name__=='__main__':
    app=QApplication(sys.argv);w=Main();w.show();sys.exit(app.exec())
