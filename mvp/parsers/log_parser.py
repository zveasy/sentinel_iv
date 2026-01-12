from mvp import analyze


def parse(path):
    return analyze.load_metrics_log(path)
