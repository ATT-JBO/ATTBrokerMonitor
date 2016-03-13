__author__ = 'Jan Bogaerts'
__copyright__ = "Copyright 2016, AllThingsTalk"
__credits__ = []
__maintainer__ = "Jan Bogaerts"
__email__ = "jb@allthingstalk.com"
__status__ = "Prototype"  # "Development", or "Production"

import kivy
kivy.require('1.9.1')   # replace with your current kivy version !

import logging
logging.getLogger().setLevel(logging.INFO)

from kivy.app import App
from kivy.uix.widget import Widget
from kivy.uix.scrollview import ScrollView
from kivy.uix.tabbedpanel import TabbedPanelItem
from kivy.uix.gridlayout import GridLayout
from kivy.properties import ObjectProperty, BooleanProperty
from kivy.uix.treeview import TreeView, TreeViewNode, TreeViewLabel


from ConfigParser import *

import attiotuserclient as IOT
from errors import *

appConfigFileName = 'app.config'

class Credentials():
    def __init__(self):
        self.userName = ''
        self.password = ''
        self.server = ''
        self.broker = ''

class CredentialsDialog(Popup):
    "set credentials"
    userNameInput = ObjectProperty()
    pwdInput = ObjectProperty()

    serverInput = ObjectProperty()
    brokerInput = ObjectProperty()

    def __init__(self, credentials, callback, **kwargs):
        self.callback = callback
        super(CredentialsDialog, self).__init__(**kwargs)
        if credentials:
            self.userNameInput.text = credentials.userName
            self.pwdInput.text = credentials.password
            if hasattr(credentials, 'server') and credentials.server:
                self.serverInput.text = credentials.server
            else:
                self.serverInput.text = 'api.smartliving.io'
            if hasattr(credentials, 'broker') and credentials.broker:
                self.brokerInput.text = credentials.broker
            else:
                self.brokerInput.text = 'broker.smartliving.io'
        else:
            self.serverInput.text = 'api.smartliving.io'
            self.brokerInput.text = 'broker.smartliving.io'

    def dismissOk(self):
        if self.callback:
            credentials = Credentials()
            credentials.userName = self.userNameInput.text
            credentials.password = self.pwdInput.text
            credentials.server = self.serverInput.text
            credentials.broker = self.brokerInput.text
            self.callback(credentials)
        self.dismiss()


class LogView(TabbedPanelItem):
    """"the main data view"""
    toCloudLayout = ObjectProperty(None)
    toClientLayout = ObjectProperty(None)

    def __init__(self, **kwargs):
        super(TabbedPanelItem, self).__init__(**kwargs)

    def register(self, assetId):
        IOT.subscribe(assetId, self.onValueFromCloud)
        desc = IOT.SubscriberData()
        desc.id = IOT.getOutPath(assetId)
        desc.callback = self.onValueFromDevice
        desc.direction = 'out'
        IOT.subscribeAdv(desc)
        self.assetId = assetId


    def onValueFromCloud(self, value):
        if 'At' in value:
            label = '{} - {}'.format(value['At'], value['Value'])
        elif 'at' in value:
            label = '{} - {}'.format(value['at'], value['value'])
        self.onValue(label, self.toClientLayout)

    def onValueFromDevice(self, value):
        self.onValue(value, self.toCloudLayout)

    def onValue(self, value, layout):
        if layout:
            logging.info(str(value))
            label = Label()
            label.halign = 'left'
            label.text = value
            label.size_hint = (1, None)
            label.size = self.texture_size
            layout.add_widget(label)

    def clear(self):
        if self.toCloudLayout:
            self.toCloudLayout.clear_widgets()
        if self.toClientLayout:
            self.toClientLayout.clear_widgets()

class MainWindow(Widget):
    documentsView = ObjectProperty(None)

    def __init__(self, **kwargs):
        super(MainWindow, self).__init__(**kwargs)

    def AddAsset(self):
        """show the add asset dialog"""
        try:
            popup = Popup(title="select asset")
            popup.size_hint = (0.8,0.8)
            tv = TreeView(root_options=dict(text='Tree One'), hide_root=True, indent_level=4)
            tv.size_hint = 1, None
            tv.bind(minimum_height = tv.setter('height'))
            tv.load_func = self.populateTreeNode
            tv.bind(selected_node=self.on_assetSelected)
            root = ScrollView(pos = (0, 0))
            root.add_widget(tv)
            popup.add_widget(root)
            popup.open()
        except Exception as e:
            showError(e)

    def populateTreeNode(self, treeview, node):
        try:
            if not node:
                grounds = IOT.getGrounds(True)
                for ground in grounds:
                    result = TreeViewLabel(text=ground['title'],is_open=False, is_leaf=False, no_selection=True)
                    result.ground_id=ground['id']
                    yield result
            elif hasattr(node, 'ground_id'):
                devices = IOT.getDevices(node.ground_id)
                for device in devices:
                    result = TreeViewLabel(is_open=False, is_leaf=False, no_selection=True)
                    result.device_id = device['id']
                    if device['title']:
                        result.text=device['title']             # for old devices that didn't ahve a title yet.
                    else:
                        result.text=device['name']
                    yield result
            elif hasattr(node, 'device_id'):
                assets = IOT.getAssets(node.device_id)
                for asset in assets:
                    result = TreeViewLabel(is_open=False, is_leaf=True)
                    result.asset_id = asset['id']
                    if asset['title']:
                        result.text=asset['title']             # for old devices that didn't ahve a title yet.
                    else:
                        result.text=asset['name']
                    yield result
        except Exception as e:
            showError(e)

    def on_assetSelected(self, instance, id):
        """add new log"""
        if instance:
            instance.parent.parent.parent.parent.dismiss()
        view = LogView()
        view.text = id.text
        view.shorten = True
        view.register(id.asset_id)
        self.documentsView.add_widget(view)
        #self.documentsView.content = view

    def removeCurrent(self):
        """remove the current view"""
        curSlide = self.documentsView.current_tab
        if curSlide:
            IOT.unsubscribe(curSlide.assetId)
            IOT.unsubscribe(IOT.getOutPath(curSlide.assetId))
            self.documentsView.remove_widget(curSlide)

    def clearCurrent(self):
        """clear the content of the current view"""
        curSlide = self.documentsView.current_tab
        if curSlide:
            curSlide.clear()

    def showCredentialsDlg(self):
        dlg = CredentialsDialog(Application.credentials, self.credentialsChanged)
        dlg.open()

    def credentialsChanged(self, newCredentials):
        IOT.disconnect(False)
        self.documentsView.clear_tabs()
        Application.credentials = newCredentials
        IOT.connect(newCredentials.userName, newCredentials.password, newCredentials.server, newCredentials.broker)
        Application.saveSettings()

class ATTBrokerMonApp(App):
    def build(self):
        self.credentials = None
        self.getSettings()
        self.connect()
        res = MainWindow()
        return res

    def connect(self):
        try:
            if self.credentials:
                IOT.connect(self.credentials.userName, self.credentials.password, self.credentials.server, self.credentials.broker)
                logging.info("connected")
        except Exception as e:
            showError(e)


    def on_pause(self):                         # can get called multiple times, sometimes no memory objects are set
        IOT.disconnect(True)
        return True

    def on_resume(self):
        self.connect()

    def on_stop(self):
        IOT.disconnect(False)

    def getSettings(self):
        self.config = ConfigParser()
        if self.config.read(appConfigFileName):
            self.credentials = Credentials()
            if self.config.has_option('general', 'userName'):
                self.credentials.userName = self.config.get('general', 'userName')
            if self.config.has_option('general', 'password'):
                self.credentials.password = self.config.get('general', 'password')
            if self.config.has_option('general', 'server'):
                self.credentials.server = self.config.get('general', 'server')
            if self.config.has_option('general', 'broker'):
                self.credentials.broker = self.config.get('general', 'broker')

    def saveSettings(self):
        if not self.config.has_section('general'):
            self.config.add_section('general')
        self.config.set('general', 'userName', self.credentials.userName)
        self.config.set('general', 'password', self.credentials.password)
        self.config.set('general', 'server', self.credentials.server)
        self.config.set('general', 'broker', self.credentials.broker)
        with open(appConfigFileName, 'w') as f:
            self.config.write(f)

Application = ATTBrokerMonApp()

if __name__ == '__main__':
    Application.run()