import type { CodegenConfig } from "@graphql-codegen/cli";

const config: CodegenConfig = {
  schema: "../../apps/api-core/schema.gql",
  documents: ["graphql/**/*.graphql"],
  generates: {
    "src/generated-graphql/graphql.ts": {
      plugins: [
        "typescript",
        "typescript-operations",
        "typescript-graphql-request",
      ],
      // Emit GraphQL enums as string-union types (e.g. SignupRole = "PATIENT" | ...)
      // so validated string values from forms assign directly without enum-member
      // mapping.
      config: { enumsAsTypes: true },
    },
  },
};

export default config;
