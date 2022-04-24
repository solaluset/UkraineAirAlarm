from tinycss2 import parse_stylesheet
from tinycss2.ast import IdentToken, LiteralToken, WhitespaceToken, FunctionBlock


class Transformer:
    def __init__(self):
        self.vars = {}
        self.overwrite = True

    def transform(self, node):
        overwrite_changed = False
        for pre in reversed(getattr(node, "prelude", ())):
            if isinstance(pre, IdentToken):
                if pre.value in self.ignore:
                    self.overwrite = False
                    overwrite_changed = True
                break
        if hasattr(node, "content"):
            name = None
            for i, token in enumerate(node.content):
                if isinstance(token, IdentToken) and token.value.startswith("--"):
                    if token.value not in self.vars or self.overwrite:
                        name = token.value
                elif name and not isinstance(token, (LiteralToken, WhitespaceToken)):
                    token = self.resolve_var(token)
                    self.vars[name] = token
                    node.content[i] = token
                    name = None
                else:
                    node.content[i] = self.resolve_var(self.transform(token))
        if overwrite_changed:
            self.overwrite = True
        return node

    def resolve_var(self, token):
        while isinstance(token, FunctionBlock) and token.name == "var":
            try:
                token = self.vars[token.arguments[0].value]
            except KeyError:
                break
        return token

    def parse(self, css: str, ignore_classes: list[str] = []):
        self.ignore = set(ignore_classes)
        return "".join(
            self.transform(node).serialize() for node in parse_stylesheet(css)
        )


def parse(css: str, ignore_classes: list[str] = []):
    return Transformer().parse(css, ignore_classes)


if __name__ == "__main__":
    with open("styles.css") as f:
        print(parse(f.read(), ["light"]))
