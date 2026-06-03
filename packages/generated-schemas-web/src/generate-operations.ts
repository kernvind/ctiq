import { readFileSync, writeFileSync, mkdirSync } from "fs";
import path from "path";
// 1. Add OperationTypeNode to your graphql imports
import { buildSchema, print, OperationTypeNode } from "graphql";
import { buildOperationNodeForField } from "@graphql-tools/utils";

const SCHEMA_PATH = path.resolve(
  __dirname,
  "../../../apps/api-core/schema.gql",
);

const DEST_DIR = path.resolve(__dirname, "../graphql");

const schemaSource = readFileSync(SCHEMA_PATH, "utf8");
const schema = buildSchema(schemaSource);

// 2. Update the first parameter type to use OperationTypeNode
function generateOperations(
  operationType: OperationTypeNode,
  folderName: string,
) {
  const rootType =
    operationType === OperationTypeNode.QUERY
      ? schema.getQueryType()
      : schema.getMutationType();

  if (!rootType) return;

  const fields = rootType.getFields();
  const targetDir = path.join(DEST_DIR, folderName);

  mkdirSync(targetDir, { recursive: true });

  for (const fieldName of Object.keys(fields)) {
    const operationAST = buildOperationNodeForField({
      schema,
      // 3. Pass the strongly-typed enum value cleanly here
      kind: operationType,
      field: fieldName,
      depthLimit: 3,
    });

    const graphqlString = print(operationAST);
    writeFileSync(path.join(targetDir, `${fieldName}.graphql`), graphqlString);
  }

  console.log(`✅ Generated ${Object.keys(fields).length} ${folderName}`);
}

// 4. Execute using the official GraphQL enum values
generateOperations(OperationTypeNode.QUERY, "queries");
generateOperations(OperationTypeNode.MUTATION, "mutations");
