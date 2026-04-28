from flask_mcp_lens.urlmap import match


class TestMatchConverters:
    def test_string_default(self):
        assert match("/users/<name>", "GET", "/users/alice", "GET") is True

    def test_string_explicit(self):
        assert match("/items/<string:slug>", "GET", "/items/hello-world", "GET") is True

    def test_int_converter(self):
        assert match("/users/<int:id>", "GET", "/users/42", "GET") is True

    def test_int_converter_rejects_non_integer(self):
        assert match("/users/<int:id>", "GET", "/users/abc", "GET") is False

    def test_float_converter(self):
        assert match("/items/<float:price>", "GET", "/items/3.14", "GET") is True

    def test_float_converter_rejects_non_float(self):
        assert match("/items/<float:price>", "GET", "/items/abc", "GET") is False

    def test_path_converter_includes_slashes(self):
        assert match("/files/<path:filename>", "GET", "/files/a/b/c.txt", "GET") is True

    def test_uuid_converter(self):
        assert match(
            "/obj/<uuid:uid>", "GET",
            "/obj/550e8400-e29b-41d4-a716-446655440000", "GET"
        ) is True

    def test_uuid_converter_rejects_non_uuid(self):
        assert match("/obj/<uuid:uid>", "GET", "/obj/not-a-uuid", "GET") is False

    def test_default_converter_rejects_slash(self):
        assert match("/a/<name>", "GET", "/a/foo/bar", "GET") is False


class TestMatchMethod:
    def test_method_mismatch(self):
        assert match("/users", "GET", "/users", "POST") is False

    def test_method_match(self):
        assert match("/users", "POST", "/users", "POST") is True


class TestMatchMultipleConverters:
    def test_multiple_converters(self):
        assert match("/a/<int:x>/b/<name>", "GET", "/a/5/b/hello", "GET") is True

    def test_multiple_converters_partial_mismatch(self):
        assert match("/a/<int:x>/b/<name>", "GET", "/a/abc/b/hello", "GET") is False


class TestMatchEdgeCases:
    def test_extra_segments_no_match(self):
        assert match("/users/<int:id>", "GET", "/users/1/extra", "GET") is False

    def test_partial_prefix_no_match(self):
        assert match("/users", "GET", "/users/extra", "GET") is False

    def test_exact_match(self):
        assert match("/ping", "GET", "/ping", "GET") is True

    def test_trailing_slash_strict(self):
        assert match("/users/", "GET", "/users", "GET") is False

    def test_no_trailing_slash_strict(self):
        assert match("/users", "GET", "/users/", "GET") is False
