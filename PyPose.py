#!/usr/bin/env python

""" 
  PyPose: Bioloid pose system for arbotiX robocontroller
  Copyright (c) 2008-2010 Michael E. Ferguson.  All right reserved.

  This program is free software; you can redistribute it and/or modify
  it under the terms of the GNU General Public License as published by
  the Free Software Foundation; either version 2 of the License, or
  (at your option) any later version.

  This program is distributed in the hope that it will be useful,
  but WITHOUT ANY WARRANTY; without even the implied warranty of
  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
  GNU General Public License for more details.

  You should have received a copy of the GNU General Public License
  along with this program; if not, write to the Free Software Foundation,
  Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
"""

import sys, time, os
sys.path.append("tools")
import wx
import serial

from ax12 import *

try:
    from drivers.drv_serial import Driver as serial_Driver
    HAS_DRIVER_SERIAL=True
except Exception:
    HAS_DRIVER_SERIAL=False
    print("Serial driver not supported!")

try:
    from drivers.dynamixel_zmq import Driver as dynamixel_zmq_Driver
    HAS_DRIVER_DZMQ=True
except Exception:
    HAS_DRIVER_DZMQ=False
    print("Driver dynamixel_zmq not supported!")


from PoseEditor import *
from SeqEditor import *
from project import *

VERSION = "PyPose/NUKE 0015"

###############################################################################
# Main editor window
class editor(wx.Frame):
    """ Implements the main window. """
    ID_NEW=wx.NewId()
    ID_OPEN=wx.NewId()
    ID_SAVE=wx.NewId()
    ID_SAVE_AS=wx.NewId()
    ID_EXIT=wx.NewId()
    ID_EXPORT=wx.NewId()
    ID_RELAX=wx.NewId()
    ID_CONNECTION=wx.NewId()
    ID_CONNECT=wx.NewId()
    ID_ABOUT=wx.NewId()
    ID_TEST=wx.NewId()
    ID_TIMER=wx.NewId()
    ID_COL_MENU=wx.NewId()
    ID_LIVE_UPDATE=wx.NewId()
    ID_2COL=wx.NewId()
    ID_3COL=wx.NewId()
    ID_4COL=wx.NewId()

    def __init__(self):
        """ Creates pose editor window. """
        wx.Frame.__init__(self, None, -1, VERSION, style = wx.DEFAULT_FRAME_STYLE & ~ (wx.RESIZE_BORDER | wx.MAXIMIZE_BOX))

        # key data for our program
        self.project = project() # holds data for our project
        self.tools = dict() # our tool instances
        self.toolIndex = dict() # existant tools
        self.saveReq = False
        self.panel = None
        self.driver = None
        self.filename = ""
        self.dirname = ""
        self.columns = 2        # column count for pose editor

        # for clearing red color on status bar
        self.timer = wx.Timer(self, self.ID_TIMER)
        self.timeout = 0

        self.connected = False
        
        # build our menu bar  
        self.menubar = wx.MenuBar()
        prjmenu = wx.Menu()
        prjmenu.Append(self.ID_NEW, "new") # dialog with name, # of servos
        prjmenu.Append(self.ID_OPEN, "open") # open file dialog
        prjmenu.Append(self.ID_SAVE,"save") # if name unknown, ask, otherwise save
        prjmenu.Append(self.ID_SAVE_AS,"save as") # ask for name, save
        prjmenu.AppendSeparator()
        prjmenu.Append(self.ID_EXIT,"exit") 
        self.menubar.Append(prjmenu, "project")

        toolsmenu = wx.Menu()
        # find our tools
        toolFiles = list()
        for file in os.listdir("tools"):
            if file[-3:] == '.py' and file != "__init__.py" and file != "ToolPane.py":
                toolFiles.append(file[0:-3])       
        # load tool names, give them IDs
        for t in toolFiles:
            module = __import__(t, globals(), locals(), ["NAME"])    
            name = getattr(module, "NAME")
            cid = wx.NewId()
            self.toolIndex[cid] = (t, name)
            toolsmenu.Append(cid,name)   
        toolsmenu.Append(self.ID_EXPORT,"export to AVR") # save as dialog
        self.menubar.Append(toolsmenu,"tools")

        self.menu_config = wx.Menu()
        self.menu_config.Append(self.ID_CONNECTION,"connection-setup") # dialog box: connection
        self.menu_config.Append(self.ID_CONNECT,"connect")

        self.menu_column = wx.Menu()        
        self.menu_column.Append(self.ID_2COL,"2 columns")
        self.menu_column.Append(self.ID_3COL,"3 columns")
        self.menu_column.Append(self.ID_4COL,"4 columns")
        self.menu_config.AppendMenu(self.ID_COL_MENU,"pose editor",self.menu_column)
        # live update
        self.live = self.menu_config.Append(self.ID_LIVE_UPDATE,"live pose update",kind=wx.ITEM_CHECK)
        #menu_config.Append(self.ID_TEST,"test") # for in-house testing of boards
        self.menubar.Append(self.menu_config, "config")    

        self.menu_help = wx.Menu()
        self.menu_help.Append(self.ID_ABOUT,"about")
        self.menubar.Append(self.menu_help,"help")

        self.SetMenuBar(self.menubar)    

        # configure events
        wx.EVT_MENU(self, self.ID_NEW, self.newFile)
        wx.EVT_MENU(self, self.ID_OPEN, self.openFile)
        wx.EVT_MENU(self, self.ID_SAVE, self.saveFile)
        wx.EVT_MENU(self, self.ID_SAVE_AS, self.saveFileAs)
        wx.EVT_MENU(self, self.ID_EXIT, sys.exit)
    
        for t in self.toolIndex.keys():
            wx.EVT_MENU(self, t, self.loadTool)
        wx.EVT_MENU(self, self.ID_EXPORT, self.export)     

        wx.EVT_MENU(self, self.ID_RELAX, self.doRelax)   
        wx.EVT_MENU(self, self.ID_CONNECTION, self.showConnectionDialog)
        wx.EVT_MENU(self, self.ID_CONNECT, self.toggleConnection)
        wx.EVT_MENU(self, self.ID_TEST, self.doTest)
        wx.EVT_MENU(self, self.ID_ABOUT, self.doAbout)
        self.Bind(wx.EVT_CLOSE, self.doClose)
        self.Bind(wx.EVT_TIMER, self.OnTimer, id=self.ID_TIMER)

        wx.EVT_MENU(self, self.ID_LIVE_UPDATE, self.setLiveUpdate)
        wx.EVT_MENU(self, self.ID_2COL, self.do2Col)
        wx.EVT_MENU(self, self.ID_3COL, self.do3Col)
        wx.EVT_MENU(self, self.ID_4COL, self.do4Col)

        # editor area       
        self.sb = self.CreateStatusBar(2)
        self.sb.SetStatusWidths([-1,250])
        self.sb.SetStatusText('not connected',1)

        self.loadTool()
        self.sb.SetStatusText('please create or open a project...',0)
        self.Centre()
        # small hack for WX 2.9
        if wx.__version__[0:3] != '2.9':
            # small hack for windows... 9-25-09 MEF
            self.SetBackgroundColour(wx.NullColor)
        self.Show(True)

    ###########################################################################
    # toolpane handling   
    def loadTool(self, e=None):
        if e == None:
            t = "PoseEditor"
        else:
            t = self.toolIndex[e.GetId()][0]  # get name of file for this tool  
            if self.tool == t:
                return
        if self.panel != None:
            self.panel.save()
            self.sizer.Remove(self.panel)
            self.panel.Destroy()
        self.ClearBackground()
        # instantiate
        module = __import__(t, globals(), locals(), [t,"STATUS"])
        panelClass = getattr(module, t)
        self.panel = panelClass(self,self.driver)
        self.sizer=wx.BoxSizer(wx.VERTICAL)
        self.sizer.Add(self.panel,1,wx.EXPAND|wx.ALL,10)
        self.SetSizer(self.sizer)
        self.SetAutoLayout(1)
        self.sizer.Fit(self)
        self.sb.SetStatusText(getattr(module,"STATUS"),0)
        self.tool = t
        self.panel.SetFocus()

    ###########################################################################
    # file handling                
    def newFile(self, e):  
        """ Open a dialog that asks for robot name and servo count. """ 
        dlg = NewProjectDialog(self, -1, "Create New Project")
        if dlg.ShowModal() == wx.ID_OK:
            self.project.new(dlg.name.GetValue(), dlg.count.GetValue(), int(dlg.resolution.GetValue()))
            self.loadTool()      
            self.sb.SetStatusText('created new project ' + self.project.name + ', please create a pose...')
            self.SetTitle(VERSION+" - " + self.project.name)
            self.panel.saveReq = True
            self.filename = ""
        dlg.Destroy()

    def openFile(self, e):
        """ Loads a robot file into the GUI. """ 
        dlg = wx.FileDialog(self, "Choose a file", self.dirname, "", "*.ppr", wx.OPEN)
        if dlg.ShowModal() == wx.ID_OK:
            self.filename = dlg.GetPath()
            self.dirname = dlg.GetDirectory()
            print("Opening: " + self.filename)            
            self.project.load(self.filename)  
            self.SetTitle(VERSION+" - " + self.project.name)
            dlg.Destroy()
            self.loadTool()
            self.sb.SetStatusText('opened ' + self.filename)

    def saveFile(self, e=None):
        """ Save a robot file from the GUI. """
        if self.filename == "": 
            dlg = wx.FileDialog(self, "Choose a file", self.dirname,"","*.ppr",wx.SAVE)
            if dlg.ShowModal() == wx.ID_OK:
                self.filename = dlg.GetPath()
                self.dirname = dlg.GetDirectory()
                dlg.Destroy()
            else:
                return  
        if self.filename[-4:] != ".ppr":
            self.filename = self.filename + ".ppr"
        self.project.saveFile(self.filename)
        self.sb.SetStatusText('saved ' + self.filename)

    def saveFileAs(self, e):
        self.filename = ""
        self.saveFile()                

    ###########################################################################
    # Export functionality
    def export(self, e):        
        """ Export a pose file for use with Sanguino Library. """
        if self.project.name == "":
            self.sb.SetBackgroundColour('RED')
            self.sb.SetStatusText('please create a project')
            self.timer.Start(20)
            return
        dlg = wx.FileDialog(self, "Choose a file", self.dirname,"","*.h",wx.SAVE)
        if dlg.ShowModal() == wx.ID_OK:
            self.project.export(dlg.GetPath())
            self.sb.SetStatusText("exported " + dlg.GetPath(),0)
            dlg.Destroy()        

    ###########################################################################
    # Port Manipulation
    def findPorts(self):
        """ return a list of serial ports """
        self.ports = list()
        # windows first
        for i in range(20):
            try:
                s = serial.Serial("COM"+str(i))
                s.close()
                self.ports.append("COM"+str(i))
            except:
                pass
        if len(self.ports) > 0:
            return self.ports
        # mac specific next:        
        try:
            for port in os.listdir("/dev/"):
                if port.startswith("tty.usbserial"):
                    self.ports.append("/dev/"+port)
        except:
            pass
        # linux/some-macs
        for k in ["/dev/ttyUSB","/dev/ttyACM","/dev/ttyS"]:
                for i in range(6):
                    try:
                        s = serial.Serial(k+str(i))
                        s.close()
                        self.ports.append(k+str(i))
                    except:
                        pass
        return self.ports
			
    def doConnect(self):
        driver_type=self.project.connection['type']
        error=False
        try:
            if driver_type == 'serial':
                if not HAS_DRIVER_SERIAL:
                    print("Connection type not supported!")
                    error=True
                else:
                    con_port=self.project.connection['settings']['serial']['port']
                    con_baudrate=self.project.connection['settings']['serial']['baudrate']
                    self.driver = serial_Driver(
                        con_port,
                        con_baudrate,
                        True
                    )

                    status_text="%s @ %i"%(con_port,con_baudrate)
            elif driver_type == 'dynamixel_zmq':
                if not HAS_DRIVER_DZMQ:
                    print("Connection type not supported!")
                    error=True
                    
                con_uri=self.project.connection['settings']['dynamixel_zmq']['uri']
                self.driver = dynamixel_zmq_Driver(
                    con_uri,
                    True
                )
                status_text="ZMQ: %s"%(con_uri)
                

        except Exception as e:
            exc_type, exc_value, exc_traceback = sys.exc_info()
            lines = traceback.format_exception(exc_type, exc_value, exc_traceback)
            exception_str="\n".join('!! ' + line for line in lines)
            print(exception_str)
            error=True
        if error:
            self.driver = None
            self.sb.SetBackgroundColour('RED')
            self.sb.SetStatusText('Could not connect with driver %s'%driver_type,0)
            self.sb.SetStatusText('not connected',1)
            self.timer.Start(20)
        else:
            self.connected=True
            self.menu_config.SetLabel(self.ID_CONNECT,'disconnect')
            self.panel.port = self.driver
            self.panel.portUpdated()
            self.sb.SetStatusText(status_text,1)
            
    def doDisconnect(self):
        if self.project.connection['type'] == 'serial':
            if self.driver:
                self.driver.close()
                self.driver=None
        self.connected=False
        self.menu_config.SetLabel(self.ID_CONNECT,'connect')

    def toggleConnection(self,e=None):
        if not self.connected:
            self.doConnect()
        else:
            self.doDisconnect()
        print("connect-toggle")
        
    def showConnectionDialog(self, e=None):
        conn_dlg=ConnectionSetup(self,-1)
        conn_dlg.Show(True)
        
    def doTest(self, e=None):
        if self.driver != None:
            self.driver.execute(253, 25, list())

    def doRelax(self, e=None):
        """ Relax servos so you can pose them. """
        if self.driver != None:
            print("PyPose: relaxing servos...")      
            for servo in range(self.project.count):
                self.driver.setReg(servo+1,P_TORQUE_ENABLE, [0,])    
        else:
            self.sb.SetBackgroundColour('RED')
            self.sb.SetStatusText("No Port Open",0) 
            self.timer.Start(20)

    def doAbout(self, e=None):
        license= """This program is free software; you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation; either version 2 of the License, or
(at your option) any later version.

This library is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
Lesser General Public License for more details.

You should have received a copy of the GNU Lesser General Public
License along with this library; if not, write to the Free Software
Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301 USA)
"""
        info = wx.AboutDialogInfo()
        info.SetName(VERSION)
        info.SetDescription("A lightweight pose and capture software for the ArbotiX robocontroller")
        info.SetCopyright("Copyright (c) 2008-2010 Michael E. Ferguson.  All right reserved.")
        info.SetLicense(license)
        info.SetWebSite("http://www.vanadiumlabs.com")
        wx.AboutBox(info)

    def doClose(self, e=None):
        # TODO: edit this to check if we NEED to save...
        if self.project.save == True:
            dlg = wx.MessageDialog(None, 'Save changes before closing?', '',
            wx.YES_NO | wx.CANCEL | wx.ICON_QUESTION)
            r = dlg.ShowModal()            
            if r == wx.ID_CANCEL:
                e.Veto()
                return
            elif r == wx.ID_YES:
                self.saveFile()
                pass
        self.Destroy()
            
    def OnTimer(self, e=None):
        self.timeout = self.timeout + 1
        if self.timeout > 50:
            self.sb.SetBackgroundColour(wx.NullColor)
            self.sb.SetStatusText("",0)
            self.sb.Refresh()
            self.timeout = 0
            self.timer.Stop()

    ###########################################################################
    # Pose Editor settings
    def do2Col(self, e=None):
        self.columns = 2
        if self.tool == "PoseEditor":
            self.loadTool()
    def do3Col(self, e=None):
        self.columns = 3
        if self.tool == "PoseEditor":
            self.loadTool()
    def do4Col(self, e=None):
        self.columns = 4
        if self.tool == "PoseEditor":
            self.loadTool()
    def setLiveUpdate(self, e=None):
        if self.tool == "PoseEditor":
            self.panel.live = self.live.IsChecked()
        
###############################################################################
# New Project Dialog
class NewProjectDialog(wx.Dialog):
    def __init__(self, parent, cid, title):
        wx.Dialog.__init__(self, parent, cid, title, size=(310, 180))  

        panel = wx.Panel(self, -1)
        vbox = wx.BoxSizer(wx.VERTICAL)

        wx.StaticBox(panel, -1, 'Project Parameters', (5, 5), (300, 120))
        wx.StaticText(panel, -1, 'Name:', (15,30))
        self.name = wx.TextCtrl(panel, -1, '', (105,25)) 
        wx.StaticText(panel, -1, '# of Servos:', (15,55))
        self.count = wx.SpinCtrl(panel, -1, '18', (105, 50), min=1, max=30)
        wx.StaticText(panel, -1, 'Resolution:', (15,80))
        self.resolution =  wx.ComboBox(panel, -1, '1024', (105, 75), choices=['1024','4096'])

        hbox = wx.BoxSizer(wx.HORIZONTAL)
        okButton = wx.Button(self, wx.ID_OK, 'Ok', size=(70, 30))
        closeButton = wx.Button(self, wx.ID_CANCEL, 'Close', size=(70, 30))
        hbox.Add(okButton, 1)
        hbox.Add(closeButton, 1, wx.LEFT, 5)

        vbox.Add(panel)
        vbox.Add(hbox, 1, wx.ALIGN_CENTER | wx.TOP | wx.BOTTOM, 10)

        self.SetSizer(vbox)

# Connection Dialog
class ConnectionSetup(wx.Frame):
    
    def __init__(self, *args, **kwds):
        kwds["style"] = wx.FRAME_FLOAT_ON_PARENT
        self.parent=args[0]
        wx.Frame.__init__(self, *args, **kwds)
        self.Centre()
        self.con_types={
            0:'serial',
            1:'dynamixel_zmq'
        }
        self.baudrates=["9600", "19200", "38400", "57600", "115200", "1000000", "2000000"]

        self.con_type = wx.Notebook(self, -1, style=0)
        
        #page for serial
        self.con_pane_serial = wx.Panel(self.con_type, -1)
        self.label_port = wx.StaticText(self.con_pane_serial, -1, "Port")
        self.combo_port = wx.ComboBox(self.con_pane_serial, -1, choices=[], style=wx.CB_DROPDOWN)
        self.label_baudrate = wx.StaticText(self.con_pane_serial, -1, "Baudrate")
        self.combo_baudrate = wx.ComboBox(self.con_pane_serial, -1, choices=self.baudrates, style=wx.CB_DROPDOWN)

        #page for dynamixel_zmq
        self.con_pane_dzmq = wx.Panel(self.con_type, -1)
        self.label_uri = wx.StaticText(self.con_pane_dzmq, -1, "URI")
        self.combo_uri = wx.ComboBox(self.con_pane_dzmq, -1, choices=["tcp://localhost:5555", "ipc:///var/run/dynamixel_zmq"], style=wx.CB_DROPDOWN)

        self.button_cancel = wx.Button(self, -1, "Cancel")
        self.button_ok = wx.Button(self, -1, "Ok")

        self.__set_properties()
        self.__do_layout()

        self.Bind(wx.EVT_BUTTON, self.doCancel, self.button_cancel)
        self.Bind(wx.EVT_BUTTON, self.doOK, self.button_ok)

    def __set_properties(self):
        self.SetTitle("Connection")
        connection_setup=self.parent.project.connection
        """
        for type_id in self.con_types:
            if connection_setup['type'] == self.con_types[type_id]:
                self.con_type.ChangeSelection(int(type_id))
        """
        
        port_list=self.parent.findPorts()
        self.combo_port.Clear()
        #fill serial_pane
        for port in port_list:
            self.combo_port.Append(port)
        if (not 'settings' in connection_setup) or (type(connection_setup['settings'])!=dict):
            connection_setup['settings']={}
        connection_settings=connection_setup['settings']
        if ('serial' in connection_settings):
            if ('port' in connection_settings['serial']) and (type(connection_settings['serial']['port'])==str):
                self.combo_port.SetValue(connection_settings['serial']['port'])
        
            if ('baudrate' in connection_settings['serial']) and (type(connection_settings['serial']['baudrate'])==int):
                self.combo_baudrate.SetValue(str(connection_settings['serial']['baudrate']))
        
        #fill dzmq_pane
        if ('dynamixel_zmq' in connection_settings):
            self.combo_uri.Clear()
            if (not 'uris' in connection_settings['dynamixel_zmq']) or (type(connection_settings['dynamixel_zmq']['uris'])!=list):
                connection_settings['dynamixel_zmq']['uris']=[]
            else:
                for uri in connection_settings['dynamixel_zmq']['uris']:
                    self.combo_uri.Append(uri)
            self.combo_uri.SetValue(connection_settings['dynamixel_zmq']['uri'])

    def __do_layout(self):
        sizer_5 = wx.BoxSizer(wx.VERTICAL)
        grid_sizer_2 = wx.GridSizer(1, 2, 0, 0)
        grid_sizer_4 = wx.GridSizer(3, 2, 0, 0)

        grid_sizer_3 = wx.GridSizer(3, 2, 0, 0)
        grid_sizer_3.Add(self.label_port, 0, wx.ALIGN_RIGHT|wx.ALIGN_CENTER_HORIZONTAL|wx.ALIGN_CENTER_VERTICAL, 0)
        grid_sizer_3.Add(self.combo_port, 0, wx.ALIGN_CENTER_HORIZONTAL|wx.ALIGN_CENTER_VERTICAL, 0)
        grid_sizer_3.Add(self.label_baudrate, 0, wx.ALIGN_CENTER_HORIZONTAL|wx.ALIGN_CENTER_VERTICAL, 0)
        grid_sizer_3.Add(self.combo_baudrate, 0, wx.ALIGN_CENTER_HORIZONTAL|wx.ALIGN_CENTER_VERTICAL, 0)
        self.con_pane_serial.SetSizer(grid_sizer_3)
        self.con_type.AddPage(self.con_pane_serial, "Serial")

        grid_sizer_4.Add(self.label_uri, 0, wx.ALIGN_CENTER_HORIZONTAL|wx.ALIGN_CENTER_VERTICAL, 0)
        grid_sizer_4.Add(self.combo_uri, 0, wx.ALIGN_CENTER_HORIZONTAL|wx.ALIGN_CENTER_VERTICAL, 0)
        self.con_pane_dzmq.SetSizer(grid_sizer_4)
        self.con_type.AddPage(self.con_pane_dzmq, "Dynamixel-ZMQ")

        sizer_5.Add(self.con_type, 1, wx.EXPAND, 0)
        grid_sizer_2.Add(self.button_cancel, 0, wx.ALIGN_CENTER_HORIZONTAL|wx.ALIGN_CENTER_VERTICAL, 0)
        grid_sizer_2.Add(self.button_ok, 0, wx.ALIGN_CENTER_HORIZONTAL|wx.ALIGN_CENTER_VERTICAL, 0)
        sizer_5.Add(grid_sizer_2, 0, wx.EXPAND, 0)
        self.SetSizer(sizer_5)
        sizer_5.Fit(self)
        self.Layout()
        # end wxGlade

    def doCancel(self, event):
        event.Skip()
        self.Destroy()

    def doOK(self, event):
        if not 'settings' in self.parent.project.connection:
            self.parent.project.connection['settings']={}
            
        new_con_type=self.con_types[self.con_type.GetSelection()]
        #some kind of a soft-pointer / don't get confused ;-)
        settings_p= self.parent.project.connection['settings']
        self.parent.project.connection['type']= new_con_type
        if new_con_type == 'serial':
            if not 'serial' in settings_p:
                settings_p['serial']={}
             
            settings_p['serial']['port']=str(self.combo_port.GetValue())
            settings_p['serial']['baudrate']=int(self.combo_baudrate.GetValue())
        elif new_con_type == 'dynamixel_zmq':
            if not 'dynamixel_zmq' in settings_p:
                settings_p['dynamixel_zmq']={}
            new_dzmq_uri=str(self.combo_uri.GetValue())
            settings_p['dynamixel_zmq']['uri']=new_dzmq_uri
            if not 'uris' in settings_p['dynamixel_zmq']:
               settings_p['dynamixel_zmq']['uris']=[]
            
            if (not new_dzmq_uri in settings_p['dynamixel_zmq']['uris']):
                settings_p['dynamixel_zmq']['uris'].append(new_dzmq_uri)         
                #max 10 of last uri's
                if len(settings_p['dynamixel_zmq']['uris'])>10:
                    settings_p['dynamixel_zmq']['uris']=settings_p['dynamixel_zmq']['uris'][1:]
        #print(settings_p)
        self.parent.project.save = True
        event.Skip()
        self.Destroy()
        
if __name__ == "__main__":
    print("PyPose starting... ")
    app = wx.App()
    frame = editor()
    app.MainLoop()

