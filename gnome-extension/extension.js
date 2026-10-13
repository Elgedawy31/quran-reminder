import Clutter from 'gi://Clutter';
import Gio from 'gi://Gio';
import GLib from 'gi://GLib';
import Pango from 'gi://Pango';
import St from 'gi://St';

import {Extension} from 'resource:///org/gnome/shell/extensions/extension.js';
import * as Main from 'resource:///org/gnome/shell/ui/main.js';

const BUS = 'io.github.Elgedawy31.QuranReminder';
const PATH = '/io/github/Elgedawy31/QuranReminder';

export default class QuranReminder extends Extension {
    enable() {
        this._enabled = true;
        this._cancellable = new Gio.Cancellable();
        this._card = new St.BoxLayout({
            style_class: 'jisr-quran-card', vertical: true,
            reactive: true, visible: false, can_focus: false,
        });
        this._reference = new St.Label({style_class: 'jisr-quran-reference'});
        this._card.add_child(this._reference);
        this._progress = new St.Label({style_class: 'jisr-quran-progress'});
        this._card.add_child(this._progress);

        this._scroll = new St.ScrollView({
            style_class: 'jisr-quran-scroll', y_expand: true,
            hscrollbar_policy: St.PolicyType.NEVER,
            vscrollbar_policy: St.PolicyType.AUTOMATIC,
        });
        const content = new St.BoxLayout({vertical: true, x_expand: true});
        this._verse = new St.Label({style_class: 'jisr-quran-verse', x_expand: true});
        this._verse.clutter_text.set_line_wrap(true);
        this._verse.clutter_text.set_line_wrap_mode(Pango.WrapMode.WORD_CHAR);
        this._verse.clutter_text.set_ellipsize(Pango.EllipsizeMode.NONE);
        content.add_child(this._verse);
        // GNOME 45 uses add_actor(); 46+ uses set_child().
        if (typeof this._scroll.set_child === 'function')
            this._scroll.set_child(content);
        else
            this._scroll.add_actor(content);
        this._card.add_child(this._scroll);

        const footer = new St.BoxLayout({
            style_class: 'jisr-quran-footer', x_align: Clutter.ActorAlign.END,
        });
        for (const [label, method] of [['إخفاء', 'Hide'], ['✓ تمت القراءة', 'ConfirmRead']]) {
            const button = new St.Button({
                label, style_class: 'jisr-quran-button',
                can_focus: false, reactive: true, track_hover: true,
                accessible_name: label,
            });
            button.connect('clicked', () => {
                if (this._number)
                    this._call(method, new GLib.Variant('(u)', [this._number]));
            });
            footer.add_child(button);
        }
        this._card.add_child(footer);
        // No modal grab or keyboard focus: other applications keep receiving keys.
        Main.layoutManager.addTopChrome(this._card, {trackFullscreen: false});
        this._monitorsId = Main.layoutManager.connect('monitors-changed', () => this._position());
        this._workareasId = global.display.connect('workareas-changed', () => this._position());
        this._watch = Gio.bus_watch_name(Gio.BusType.SESSION, BUS, Gio.BusNameWatcherFlags.NONE,
            (_connection, _name, owner) => this._connect(owner),
            () => {
                this._owner = null;
                this._disconnectProxy();
                this._card?.hide();
            });
    }

    _position() {
        if (!Main.layoutManager.primaryMonitor || !this._card)
            return;
        const area = Main.layoutManager.getWorkAreaForMonitor(Main.layoutManager.primaryIndex);
        const width = Math.max(240, Math.min(1040, area.width - 64));
        const height = Math.max(240, Math.min(480, area.height - 64));
        this._card.set_size(width, height);
        this._card.set_position(area.x + Math.round((area.width - width) / 2),
            area.y + Math.round((area.height - height) / 2));
    }

    _disconnectProxy() {
        if (this._proxy && this._proxySignal)
            this._proxy.disconnect(this._proxySignal);
        this._proxySignal = null;
        this._proxy = null;
    }

    _connect(owner) {
        this._owner = owner;
        this._disconnectProxy();
        Gio.DBusProxy.new_for_bus(Gio.BusType.SESSION, Gio.DBusProxyFlags.DO_NOT_AUTO_START,
            null, BUS, PATH, BUS, this._cancellable, (_source, result) => {
                try {
                    const proxy = Gio.DBusProxy.new_for_bus_finish(result);
                    if (!this._enabled || this._owner !== owner)
                        return;
                    this._proxy = proxy;
                    this._proxySignal = proxy.connect('g-signal', (_proxy, _sender, signal, parameters) => {
                        if (signal === 'StateChanged')
                            this._render(parameters.deepUnpack()[0]);
                    });
                    this._call('Attach', null, reply => this._render(reply.deepUnpack()[0]));
                } catch (error) {
                    if (!error.matches(Gio.IOErrorEnum, Gio.IOErrorEnum.CANCELLED))
                        console.error(`Jisr Quran: ${error.message}`);
                }
            });
    }

    _call(method, parameters, callback = null) {
        const proxy = this._proxy;
        if (!proxy)
            return;
        proxy.call(method, parameters, Gio.DBusCallFlags.NONE, 5000, this._cancellable,
            (_source, result) => {
                try {
                    const reply = proxy.call_finish(result);
                    if (this._enabled && this._proxy === proxy)
                        callback?.(reply);
                } catch (error) {
                    if (!error.matches(Gio.IOErrorEnum, Gio.IOErrorEnum.CANCELLED))
                        console.error(`Jisr Quran: ${error.message}`);
                }
            });
    }

    _render(json) {
        if (!this._enabled)
            return;
        const state = JSON.parse(json);
        this._card.remove_all_transitions();
        if (!state.running || !state.visible) {
            this._card.ease({opacity: 0, duration: 200,
                onComplete: () => this._card?.hide()});
            return;
        }
        this._number = state.number;
        this._reference.set_text(`آية من القرآن · ${state.reference}`);
        this._progress.set_text(`قرأت ${state.read_count} من ${state.total_ayahs} آية · ${state.percent_read.toFixed(2)}%`);
        this._verse.set_text(state.arabic);
        this._position();
        const wasVisible = this._card.visible;
        if (!wasVisible) {
            const adjustment = this._scroll.vscroll?.adjustment ?? this._scroll.vadjustment;
            adjustment?.set_value(0);
            this._card.opacity = 0;
        }
        this._card.show();
        this._card.ease({opacity: 255, duration: 300, mode: Clutter.AnimationMode.EASE_OUT_CUBIC});
    }

    disable() {
        this._enabled = false;
        // GNOME keeps its bus connection while the extension is disabled/locked.
        this._proxy?.call('Detach', null, Gio.DBusCallFlags.NONE, 1000, null, null);
        this._cancellable?.cancel();
        if (this._watch)
            Gio.bus_unwatch_name(this._watch);
        this._watch = null;
        this._owner = null;
        this._disconnectProxy();
        if (this._monitorsId)
            Main.layoutManager.disconnect(this._monitorsId);
        if (this._workareasId)
            global.display.disconnect(this._workareasId);
        this._monitorsId = this._workareasId = null;
        this._card?.remove_all_transitions();
        this._card?.destroy();
        this._card = null;
        this._reference = this._progress = this._verse = this._scroll = null;
        this._cancellable = null;
    }
}
