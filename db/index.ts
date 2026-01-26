import { neon } from '@netlify/neon';
import { drizzle } from 'drizzle-orm/neon-http';

import * as schema from './schema';

const connectionString = process.env.NETLIFY_DATABASE_URL || process.env.DATABASE_URL;

// Lazily initialize the database connection to prevent build-time errors
// when the connection string is missing in CI/CD environments.
const getDb = () => {
    const url = process.env.NETLIFY_DATABASE_URL || process.env.DATABASE_URL;
    if (!url) {
        // Return a mock during build time if URL is missing
        return {
            select: () => ({
                from: () => ({
                    orderBy: () => []
                })
            })
        } as any;
    }
    const client = neon(url);
    return drizzle({ schema, client });
};

export const db = new Proxy({} as any, {
    get(target, prop, receiver) {
        const actualDb = getDb();
        return Reflect.get(actualDb, prop, receiver);
    }
});
