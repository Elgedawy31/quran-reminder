import Gio from 'gi://Gio';
import {Extension} from 'resource:///org/gnome/shell/extensions/extension.js';
import * as Main from 'resource:///org/gnome/shell/ui/main.js';

const XML = `<node><interface name="io.github.Elgedawy31.QuranTest">
    <method name="Snapshot"><arg direction="out" type="s"/></method>
    <method name="Click"><arg direction="in" type="u"/></method>
</interface></node>`;

export default class TestProbe extends Extension {
    enable() {
        this._object = Gio.DBusExportedObject.wrapJSObject(XML, this);
        this._object.export(Gio.DBus.session, '/io/github/Elgedawy31/QuranTest');
    }

    Snapshot() {
        const extension = Main.extensionManager.lookup('jisr-quran@elgedawy31.github.io');
        const frontend = extension?.stateObj;
        const card = frontend?._card;
        const adjustment = frontend?._scroll?.vadjustment ?? frontend?._scroll?.vscroll?.adjustment;
        return JSON.stringify({
            state: extension?.state, errors: extension?.errors,
            visible: card?.visible, opacity: card?.opacity,
            width: card?.width, height: card?.height, x: card?.x, y: card?.y,
            verse: frontend?._verse?.get_text(), number: frontend?._number,
            keyboardFocus: global.stage.key_focus === card,
            connected: Boolean(frontend?._proxy),
            scrollUpper: adjustment?.upper, scrollPageSize: adjustment?.page_size,
        });
    }

    Click(index) {
        const frontend = Main.extensionManager.lookup('jisr-quran@elgedawy31.github.io').stateObj;
        frontend._card.get_last_child().get_children()[index].emit('clicked', 1);
    }

    disable() {
        this._object?.unexport();
        this._object = null;
    }
}
