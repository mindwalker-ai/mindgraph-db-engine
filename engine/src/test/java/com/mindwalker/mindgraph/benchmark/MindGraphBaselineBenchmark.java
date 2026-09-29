/*
 * Copyright © 2026 Mindwalker
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *     http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 *
 * SPDX-FileCopyrightText: 2026 Mindwalker
 * SPDX-License-Identifier: Apache-2.0
 */
package com.mindwalker.mindgraph.benchmark;

import com.arcadedb.database.Database;
import com.arcadedb.database.DatabaseFactory;
import com.arcadedb.graph.MutableVertex;
import com.arcadedb.graph.Vertex;
import com.arcadedb.query.sql.executor.Result;
import com.arcadedb.query.sql.executor.ResultSet;
import com.arcadedb.schema.Schema;
import com.arcadedb.schema.Type;
import com.arcadedb.schema.VertexType;
import com.arcadedb.utility.FileUtils;
import org.junit.jupiter.api.Tag;
import org.junit.jupiter.api.Test;

import java.io.File;
import java.io.IOException;
import java.lang.management.ManagementFactory;
import java.lang.management.MemoryUsage;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.time.Instant;
import java.util.Arrays;
import java.util.Locale;
import java.util.Random;

import static org.assertj.core.api.Assertions.assertThat;

/**
 * Deterministic baseline benchmark owned by Mindwalker.
 *
 * <p>This is not a vendor comparison. It records a repeatable local baseline so that changes to the
 * MindGraph fork can be compared with the same source, dataset, JVM, and hardware profile.
 */
@Tag("benchmark")
class MindGraphBaselineBenchmark {
  private static final int    VERTEX_COUNT         = positiveIntegerProperty("mindgraph.benchmark.vertices", 100_000);
  private static final int    EDGE_COUNT           = positiveIntegerProperty("mindgraph.benchmark.edges", 400_000);
  private static final int    LOOKUP_WARMUP        = positiveIntegerProperty("mindgraph.benchmark.lookupWarmup", 2_000);
  private static final int    LOOKUP_ITERATIONS    = positiveIntegerProperty("mindgraph.benchmark.lookupIterations", 20_000);
  private static final int    TRAVERSAL_WARMUP     = positiveIntegerProperty("mindgraph.benchmark.traversalWarmup", 1_000);
  private static final int    TRAVERSAL_ITERATIONS = positiveIntegerProperty("mindgraph.benchmark.traversalIterations", 10_000);
  private static final String DATABASE_PATH        = "target/databases/mindgraph-baseline";

  @Test
  void recordsReproducibleGraphBaseline() throws IOException {
    final File databaseDirectory = new File(DATABASE_PATH);
    FileUtils.deleteRecursively(databaseDirectory);

    Database database = null;
    try {
      final long loadStarted = System.nanoTime();
      database = new DatabaseFactory(DATABASE_PATH).create();
      createDataset(database);
      final long loadNanos = System.nanoTime() - loadStarted;

      database.close();
      database = null;

      final long reopenStarted = System.nanoTime();
      database = new DatabaseFactory(DATABASE_PATH).open();
      final long reopenNanos = System.nanoTime() - reopenStarted;
      final Database activeDatabase = database;

      for (int i = 0; i < LOOKUP_WARMUP; i++)
        lookup(activeDatabase, i % VERTEX_COUNT);

      final Measurement lookup = measure(LOOKUP_ITERATIONS, iteration -> lookup(activeDatabase, iteration % VERTEX_COUNT));

      for (int i = 0; i < TRAVERSAL_WARMUP; i++)
        traverse(activeDatabase, i % VERTEX_COUNT);

      final Measurement traversal = measure(TRAVERSAL_ITERATIONS,
          iteration -> traverse(activeDatabase, iteration % VERTEX_COUNT));

      assertThat(lookup.operations).isEqualTo(LOOKUP_ITERATIONS);
      assertThat(traversal.operations).isEqualTo(TRAVERSAL_ITERATIONS);

      final long diskBytes = directorySize(Path.of(DATABASE_PATH));
      final MemoryUsage heap = ManagementFactory.getMemoryMXBean().getHeapMemoryUsage();
      final Path output = Path.of(System.getProperty("mindgraph.benchmark.output",
          "target/mindgraph-baseline.json"));
      Files.createDirectories(output.toAbsolutePath().getParent());
      Files.writeString(output, report(loadNanos, reopenNanos, lookup, traversal, diskBytes, heap),
          StandardCharsets.UTF_8);

      System.out.printf(Locale.ROOT,
          "MindGraph baseline: load=%.2fs reopen=%.2fms lookup[p50=%.3fms p95=%.3fms p99=%.3fms] "
              + "traversal[p50=%.3fms p95=%.3fms p99=%.3fms]%n",
          nanosToSeconds(loadNanos), nanosToMillis(reopenNanos),
          lookup.p50Millis(), lookup.p95Millis(), lookup.p99Millis(),
          traversal.p50Millis(), traversal.p95Millis(), traversal.p99Millis());
    } finally {
      if (database != null && database.isOpen())
        database.close();
      FileUtils.deleteRecursively(databaseDirectory);
    }
  }

  private static void createDataset(final Database database) {
    database.transaction(() -> {
      final Schema schema = database.getSchema();
      final VertexType account = schema.createVertexType("Account");
      account.createProperty("id", Type.INTEGER);
      account.createProperty("name", Type.STRING);
      account.createTypeIndex(Schema.INDEX_TYPE.LSM_TREE, true, "id");
      schema.createEdgeType("LINK");
    });

    final MutableVertex[] vertices = new MutableVertex[VERTEX_COUNT];
    database.begin();
    for (int i = 0; i < VERTEX_COUNT; i++) {
      vertices[i] = database.newVertex("Account")
          .set("id", i)
          .set("name", "Account-" + i)
          .save();
      if ((i + 1) % 1_000 == 0) {
        database.commit();
        database.begin();
      }
    }
    database.commit();

    final Random random = new Random(42L);
    database.begin();
    for (int i = 0; i < EDGE_COUNT; i++) {
      final int source = random.nextInt(VERTEX_COUNT);
      int target = random.nextInt(VERTEX_COUNT);
      if (target == source)
        target = (target + 1) % VERTEX_COUNT;
      vertices[source].newLightEdge("LINK", vertices[target]);
      if ((i + 1) % 2_000 == 0) {
        database.commit();
        database.begin();
      }
    }
    database.commit();
  }

  private static int lookup(final Database database, final int id) {
    try (ResultSet resultSet = database.query("sql", "SELECT FROM Account WHERE id = ?", id)) {
      assertThat(resultSet.hasNext()).isTrue();
      resultSet.next();
      return 1;
    }
  }

  private static int traverse(final Database database, final int id) {
    try (ResultSet resultSet = database.query("sql", "SELECT FROM Account WHERE id = ?", id)) {
      assertThat(resultSet.hasNext()).isTrue();
      final Result result = resultSet.next();
      final Vertex vertex = result.toElement().asVertex();
      int count = 0;
      for (Vertex ignored : vertex.getVertices(Vertex.DIRECTION.OUT, "LINK"))
        count++;
      return count;
    }
  }

  private static Measurement measure(final int iterations, final Operation operation) {
    final long[] nanos = new long[iterations];
    long resultCount = 0;
    final long started = System.nanoTime();
    for (int i = 0; i < iterations; i++) {
      final long operationStarted = System.nanoTime();
      resultCount += operation.run(i);
      nanos[i] = System.nanoTime() - operationStarted;
    }
    final long totalNanos = System.nanoTime() - started;
    Arrays.sort(nanos);
    return new Measurement(iterations, resultCount, totalNanos, nanos);
  }

  private static long directorySize(final Path path) throws IOException {
    try (var files = Files.walk(path)) {
      return files.filter(Files::isRegularFile).mapToLong(file -> {
        try {
          return Files.size(file);
        } catch (IOException ignored) {
          return 0L;
        }
      }).sum();
    }
  }

  private static String report(final long loadNanos, final long reopenNanos, final Measurement lookup,
      final Measurement traversal, final long diskBytes, final MemoryUsage heap) {
    final Runtime runtime = Runtime.getRuntime();
    return String.format(Locale.ROOT, """
        {
          "schemaVersion": 1,
          "generatedAt": "%s",
          "benchmark": "mindgraph-baseline",
          "dataset": {
            "vertices": %d,
            "edges": %d,
            "seed": 42
          },
          "measurement": {
            "lookupWarmupOperations": %d,
            "lookupMeasuredOperations": %d,
            "traversalWarmupOperations": %d,
            "traversalMeasuredOperations": %d
          },
          "environment": {
            "javaVersion": "%s",
            "javaVendor": "%s",
            "osName": "%s",
            "osVersion": "%s",
            "architecture": "%s",
            "availableProcessors": %d,
            "systemLoadAverage": %.4f,
            "maxHeapBytes": %d,
            "usedHeapBytes": %d
          },
          "storage": {
            "loadSeconds": %.6f,
            "recordsPerSecond": %.3f,
            "reopenMillis": %.6f,
            "databaseBytes": %d
          },
          "indexedLookup": %s,
          "oneHopTraversal": %s
        }
        """,
        Instant.now(),
        VERTEX_COUNT,
        EDGE_COUNT,
        LOOKUP_WARMUP,
        LOOKUP_ITERATIONS,
        TRAVERSAL_WARMUP,
        TRAVERSAL_ITERATIONS,
        escape(System.getProperty("java.version")),
        escape(System.getProperty("java.vendor")),
        escape(System.getProperty("os.name")),
        escape(System.getProperty("os.version")),
        escape(System.getProperty("os.arch")),
        runtime.availableProcessors(),
        ManagementFactory.getOperatingSystemMXBean().getSystemLoadAverage(),
        heap.getMax(),
        heap.getUsed(),
        nanosToSeconds(loadNanos),
        (VERTEX_COUNT + EDGE_COUNT) / nanosToSeconds(loadNanos),
        nanosToMillis(reopenNanos),
        diskBytes,
        lookup.toJson(),
        traversal.toJson());
  }

  private static String escape(final String value) {
    return value.replace("\\", "\\\\").replace("\"", "\\\"");
  }

  private static int positiveIntegerProperty(final String name, final int defaultValue) {
    final int value = Integer.getInteger(name, defaultValue);
    if (value <= 0)
      throw new IllegalArgumentException(name + " must be a positive integer");
    return value;
  }

  private static double nanosToSeconds(final long nanos) {
    return nanos / 1_000_000_000.0;
  }

  private static double nanosToMillis(final long nanos) {
    return nanos / 1_000_000.0;
  }

  @FunctionalInterface
  private interface Operation {
    int run(int iteration);
  }

  private record Measurement(int operations, long results, long totalNanos, long[] sortedNanos) {
    private double p50Millis() {
      return percentileMillis(0.50);
    }

    private double p95Millis() {
      return percentileMillis(0.95);
    }

    private double p99Millis() {
      return percentileMillis(0.99);
    }

    private double percentileMillis(final double percentile) {
      final int index = Math.min((int) Math.ceil(sortedNanos.length * percentile) - 1, sortedNanos.length - 1);
      return nanosToMillis(sortedNanos[Math.max(index, 0)]);
    }

    private String toJson() {
      final double seconds = nanosToSeconds(totalNanos);
      return String.format(Locale.ROOT, """
          {
              "operations": %d,
              "results": %d,
              "throughputOpsPerSecond": %.3f,
              "p50Millis": %.6f,
              "p95Millis": %.6f,
              "p99Millis": %.6f
            }""",
          operations,
          results,
          operations / seconds,
          p50Millis(),
          p95Millis(),
          p99Millis());
    }
  }
}
