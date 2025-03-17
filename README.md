# Introduction

This library provides:

- An abstract base poller that either polls a single batch or keeps poll batches until  interrupted.
- A AWS SQS poller that processes messages in the same batch concurrently via async IO, with auto message deletion.

For usage examples, please refer to tests.
