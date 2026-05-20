import { GraphQLClient } from "graphql-request";
import { getSdk } from "./generated-graphql/graphql";

const endpoint = `${process.env.BACKEND_URL}/graphql`;

export const graphqlClient = new GraphQLClient(endpoint);
export const sdk = getSdk(graphqlClient);

export function getAuthedSdk(token: string) {
  const client = new GraphQLClient(endpoint, {
    headers: { Authorization: `Bearer ${token}` },
  });
  return getSdk(client);
}
