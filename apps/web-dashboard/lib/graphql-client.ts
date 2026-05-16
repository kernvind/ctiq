import { GraphQLClient } from 'graphql-request';

const endpoint = `${process.env.BACKEND_URL}/graphql`;

export const graphqlClient = new GraphQLClient(endpoint);

export function getAuthedClient(token: string): GraphQLClient {
  return new GraphQLClient(endpoint, {
    headers: { Authorization: `Bearer ${token}` },
  });
}
