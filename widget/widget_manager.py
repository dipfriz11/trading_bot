from widget.widget import Widget


class WidgetManager:

    def __init__(self):
        self.widgets = {}

    def create_widget(self, config, exchange):
        widget = Widget(config, exchange)
        self.widgets[widget.id] = widget
        return widget

    def get_widget(self, widget_id):
        return self.widgets.get(widget_id)

    def start_widget(self, widget_id):
        widget = self.get_widget(widget_id)
        if widget:
            widget.start()

    def stop_widget(self, widget_id):
        widget = self.get_widget(widget_id)
        if widget:
            widget.stop()

    def set_stop_new(self, widget_id, enabled, mode="entries_only"):
        widget = self.get_widget(widget_id)
        if widget:
            widget.set_stop_new(enabled, mode)
