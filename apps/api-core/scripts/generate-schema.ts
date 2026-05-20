import { config } from 'dotenv';
config({ path: '.env' });

import { NestFactory } from '@nestjs/core';
import { AppModule } from '../src/app.module';

async function generateSchema() {
  const app = await NestFactory.createApplicationContext(AppModule, {
    logger: ['error'],
  });
  await app.close();
  console.log('schema.gql generated successfully');
}

generateSchema().catch((err) => {
  console.error('Failed to generate schema:', err);
  process.exit(1);
});
