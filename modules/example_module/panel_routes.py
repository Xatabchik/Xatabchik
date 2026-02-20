from flask import Blueprint, render_template

bp = Blueprint(
    "example_module",
    __name__,
    url_prefix="/modules/example_module",
    template_folder="templates",
)


@bp.route("/")
def index():
    return render_template("modules/example_module/index.html")
