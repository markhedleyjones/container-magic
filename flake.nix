{
  description = "container-magic: rapidly create containerised development environments";

  inputs.nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
  inputs.flake-utils.url = "github:numtide/flake-utils";

  outputs =
    { self, nixpkgs, flake-utils }:
    flake-utils.lib.eachDefaultSystem (
      system:
      let
        pkgs = nixpkgs.legacyPackages.${system};
        # Track the version published by semantic-release rather than duplicating it.
        version = (builtins.fromTOML (builtins.readFile ./pyproject.toml)).project.version;
      in
      {
        packages.default = pkgs.python3Packages.buildPythonApplication {
          pname = "container-magic";
          inherit version;
          src = self;
          pyproject = true;

          build-system = [ pkgs.python3Packages.setuptools ];

          dependencies = with pkgs.python3Packages; [
            pyyaml
            jinja2
            click
            pydantic
            requests
          ];

          # cm shells out to a container runtime (podman/docker) found in PATH at
          # run time; it deliberately isn't bundled, so the consumer provides it.
          # cm's own test suite needs that runtime, which the Nix sandbox lacks.
          doCheck = false;
        };

        apps.default = {
          type = "app";
          program = "${self.packages.${system}.default}/bin/cm";
        };
      }
    )
    // {
      overlays.default = final: prev: {
        container-magic = self.packages.${final.system}.default;
      };
    };
}
