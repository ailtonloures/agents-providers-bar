import Clutter from 'gi://Clutter';
import Gio from 'gi://Gio';
import GLib from 'gi://GLib';
import GObject from 'gi://GObject';
import St from 'gi://St';

import {Extension} from 'resource:///org/gnome/shell/extensions/extension.js';
import * as Main from 'resource:///org/gnome/shell/ui/main.js';
import * as PanelMenu from 'resource:///org/gnome/shell/ui/panelMenu.js';
import * as PopupMenu from 'resource:///org/gnome/shell/ui/popupMenu.js';

const REFRESH_INTERVAL_SECONDS = 300;
const BAR_TRACK_WIDTH_PX = 270;

function severitySuffix(percent) {
    if (percent >= 85)
        return 'crit';
    if (percent >= 60)
        return 'warn';
    return 'ok';
}

const AgentsUsageIndicator = GObject.registerClass(
class AgentsUsageIndicator extends PanelMenu.Button {
    _init(extensionPath) {
        super._init(0.0, 'Agents Providers Usage Bar');

        this._extensionPath = extensionPath;
        this._destroyed = false;
        this._isLoading = false;

        const iconPath = `${extensionPath}/icons/provider-bar-symbolic.svg`;
        this._icon = new St.Icon({
            gicon: Gio.icon_new_for_string(iconPath),
            style_class: 'system-status-icon apb-panel-icon apb-icon-muted',
        });
        this.add_child(this._icon);

        this.menu.box.add_style_class_name('apb-popup-box');

        this._containerItem = new PopupMenu.PopupBaseMenuItem({
            reactive: false,
            can_focus: false,
        });
        this._containerItem.add_style_class_name('apb-menu-item');
        this._container = new St.BoxLayout({
            vertical: true,
            style_class: 'apb-menu-container',
            x_expand: true,
        });
        this._containerItem.add_child(this._container);
        this.menu.addMenuItem(this._containerItem);

        this._buildHeader();
        this._cardsBox = new St.BoxLayout({
            vertical: true,
            style: 'spacing: 8px;',
            x_expand: true,
        });
        this._container.add_child(this._cardsBox);

        this._renderLoading();
        this._refresh(false);

        this._timerId = GLib.timeout_add_seconds(
            GLib.PRIORITY_DEFAULT,
            REFRESH_INTERVAL_SECONDS,
            () => {
                this._refresh(false);
                return GLib.SOURCE_CONTINUE;
            }
        );
    }

    _buildHeader() {
        const header = new St.BoxLayout({
            vertical: false,
            style_class: 'apb-header',
            x_expand: true,
        });

        const title = new St.Label({
            text: 'Agents Usage',
            style_class: 'apb-title',
            y_align: Clutter.ActorAlign.CENTER,
            x_expand: true,
        });

        this._updatedLabel = new St.Label({
            text: 'Loading...',
            style_class: 'apb-updated',
            y_align: Clutter.ActorAlign.CENTER,
        });

        const refreshBtn = new St.Button({
            style_class: 'apb-refresh-btn',
            can_focus: true,
            child: new St.Icon({
                icon_name: 'view-refresh-symbolic',
                icon_size: 14,
            }),
        });
        refreshBtn.connect('clicked', () => this._refresh(true));

        header.add_child(title);
        header.add_child(this._updatedLabel);
        header.add_child(refreshBtn);
        this._container.add_child(header);
    }

    _setPanelIconState(stateClass) {
        for (const cls of ['apb-icon-ok', 'apb-icon-warn', 'apb-icon-crit', 'apb-icon-muted'])
            this._icon.remove_style_class_name(cls);
        this._icon.add_style_class_name(stateClass);
    }

    _renderLoading() {
        this._cardsBox.destroy_all_children();
        this._cardsBox.add_child(new St.Label({
            text: 'Fetching subscription quotas...',
            style_class: 'apb-window-meta',
        }));
    }

    _resolveCliBinary() {
        const localBin = GLib.build_filenamev([GLib.get_home_dir(), '.local', 'bin', 'agents-usage']);
        if (GLib.file_test(localBin, GLib.FileTest.IS_EXECUTABLE))
            return localBin;
        return 'agents-usage';
    }

    _refresh(noCache) {
        if (this._isLoading || this._destroyed)
            return;

        this._isLoading = true;
        this._updatedLabel.set_text('Updating...');

        const argv = [this._resolveCliBinary(), '--json'];
        if (noCache)
            argv.push('--no-cache');

        try {
            const proc = Gio.Subprocess.new(
                argv,
                Gio.SubprocessFlags.STDOUT_PIPE | Gio.SubprocessFlags.STDERR_PIPE
            );
            proc.communicate_utf8_async(null, null, (subproc, res) => {
                this._isLoading = false;
                if (this._destroyed)
                    return;
                try {
                    const [, stdout, stderr] = subproc.communicate_utf8_finish(res);
                    if (!subproc.get_successful()) {
                        this._renderError(stderr || 'agents-usage exited with an error');
                        return;
                    }
                    const report = JSON.parse(stdout);
                    this._renderReport(report);
                } catch (err) {
                    this._renderError(err.message);
                }
            });
        } catch (err) {
            this._isLoading = false;
            this._renderError(`Failed to run agents-usage: ${err.message}`);
        }
    }

    _renderError(message) {
        this._setPanelIconState('apb-icon-muted');
        this._updatedLabel.set_text('Error');
        this._cardsBox.destroy_all_children();
        this._cardsBox.add_child(new St.Label({
            text: message,
            style_class: 'apb-error-text',
        }));
    }

    _renderReport(report) {
        this._cardsBox.destroy_all_children();

        const now = GLib.DateTime.new_now_local();
        this._updatedLabel.set_text(now.format('%H:%M'));

        const providers = Array.isArray(report.providers) ? report.providers : [];
        const hasAnyData = providers.some(p => Array.isArray(p.windows) && p.windows.length > 0);
        if (hasAnyData) {
            const maxPct = Number(report.overall_max_used_percent || 0);
            this._setPanelIconState(`apb-icon-${severitySuffix(maxPct)}`);
        } else {
            this._setPanelIconState('apb-icon-muted');
        }

        for (const provider of providers)
            this._cardsBox.add_child(this._buildProviderCard(provider));
    }

    _buildProviderCard(provider) {
        const card = new St.BoxLayout({
            vertical: true,
            style_class: 'apb-card',
            x_expand: true,
        });

        const header = new St.BoxLayout({
            vertical: false,
            style_class: 'apb-card-header',
            x_expand: true,
        });

        header.add_child(new St.Label({
            text: provider.display_name || provider.provider,
            style_class: 'apb-provider-name',
            x_expand: true,
            y_align: Clutter.ActorAlign.CENTER,
        }));

        if (provider.plan_name) {
            header.add_child(new St.Label({
                text: provider.plan_name,
                style_class: 'apb-plan-badge',
                y_align: Clutter.ActorAlign.CENTER,
            }));
        }
        card.add_child(header);

        if (provider.error_message) {
            card.add_child(new St.Label({
                text: provider.error_message,
                style_class: 'apb-error-text',
            }));
        }

        const windows = Array.isArray(provider.windows) ? provider.windows : [];
        if (windows.length === 0 && !provider.error_message) {
            card.add_child(new St.Label({
                text: 'No quota data available.',
                style_class: 'apb-window-meta',
            }));
        }

        for (const win of windows)
            card.add_child(this._buildWindowRow(win));

        return card;
    }

    _buildWindowRow(win) {
        const row = new St.BoxLayout({
            vertical: true,
            style_class: 'apb-window-row',
            x_expand: true,
        });

        const top = new St.BoxLayout({
            vertical: false,
            x_expand: true,
        });

        top.add_child(new St.Label({
            text: win.label,
            style_class: 'apb-window-label',
            x_expand: true,
        }));

        const pct = Math.round(Number(win.used_percent || 0));
        const resetTxt = win.reset_in_human ? ` · ${win.reset_in_human}` : '';
        top.add_child(new St.Label({
            text: `${pct}%${resetTxt}`,
            style_class: 'apb-window-meta',
        }));
        row.add_child(top);

        const track = new St.BoxLayout({
            style_class: 'apb-bar-track',
            style: `width: ${BAR_TRACK_WIDTH_PX}px;`,
        });

        const fillWidth = Math.max(4, Math.round((Math.min(100, Math.max(0, pct)) / 100) * BAR_TRACK_WIDTH_PX));
        const fill = new St.Widget({
            style_class: `apb-bar-fill apb-fill-${severitySuffix(pct)}`,
            style: `width: ${fillWidth}px;`,
        });

        track.add_child(fill);
        row.add_child(track);
        return row;
    }

    destroy() {
        this._destroyed = true;
        if (this._timerId) {
            GLib.source_remove(this._timerId);
            this._timerId = null;
        }
        super.destroy();
    }
});

export default class AgentsProvidersBarExtension extends Extension {
    enable() {
        this._indicator = new AgentsUsageIndicator(this.path);
        Main.panel.addToStatusArea(this.uuid, this._indicator);
    }

    disable() {
        if (this._indicator) {
            this._indicator.destroy();
            this._indicator = null;
        }
    }
}
